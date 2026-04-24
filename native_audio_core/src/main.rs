use std::collections::VecDeque;
use std::io::{self, BufRead, Write};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, RecvTimeoutError, Sender};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine;
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{Device, Host, HostId, SampleFormat, Stream, StreamConfig, SupportedStreamConfigRange};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

#[derive(Serialize)]
struct DeviceInfo {
    id: String,
    name: String,
    kind: String,
    channels: u16,
    sample_rates: Vec<u32>,
    virtual_device: bool,
}

#[derive(Serialize)]
struct DeviceSnapshot {
    backend: String,
    devices: Vec<DeviceInfo>,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "cmd", rename_all = "kebab-case")]
enum Command {
    Health,
    ListDevices,
    StartCapture(CaptureConfig),
    StopCapture,
    Shutdown,
}

#[derive(Debug, Deserialize, Clone)]
struct CaptureConfig {
    channel: String,
    device_id: String,
    sample_rate: Option<u32>,
    chunk_ms: Option<u32>,
    noise_gate_db: Option<f32>,
    silence_hold_ms: Option<u32>,
    pre_roll_ms: Option<u32>,
    input_gain: Option<f32>,
    enable_agc: Option<bool>,
    agc_target_dbfs: Option<f32>,
    max_agc_gain: Option<f32>,
}

#[derive(Debug)]
enum CoreEvent {
    AudioChunk(AudioChunkEvent),
    Metrics(MetricsEvent),
    Error(String),
}

#[derive(Debug)]
struct AudioChunkEvent {
    channel: String,
    seq: u64,
    sample_rate: u32,
    duration_ms: u32,
    speech: bool,
    level_db: f32,
    queue_depth: usize,
    dropped_silent_chunks: u64,
    pcm16: Vec<i16>,
}

#[derive(Debug)]
struct MetricsEvent {
    channel: String,
    sample_rate: u32,
    level_db: f32,
    speech: bool,
    queue_depth: usize,
    dropped_silent_chunks: u64,
}

struct CaptureRuntime {
    stop: Arc<AtomicBool>,
    stream: Stream,
}

fn native_host_id() -> HostId {
    #[cfg(target_os = "windows")]
    {
        HostId::Wasapi
    }
    #[cfg(target_os = "macos")]
    {
        HostId::CoreAudio
    }
    #[cfg(target_os = "linux")]
    {
        HostId::Alsa
    }
    #[cfg(not(any(target_os = "windows", target_os = "macos", target_os = "linux")))]
    {
        cpal::default_host().id()
    }
}

fn native_host() -> Result<(HostId, Host), String> {
    let host_id = native_host_id();
    let host = cpal::host_from_id(host_id).map_err(|err| err.to_string())?;
    Ok((host_id, host))
}

fn config_rates(configs: impl Iterator<Item = SupportedStreamConfigRange>) -> (u16, Vec<u32>) {
    let mut channels = 0;
    let mut rates = Vec::new();
    for config in configs {
        channels = channels.max(config.channels());
        rates.push(config.min_sample_rate().0);
        rates.push(config.max_sample_rate().0);
    }
    rates.sort_unstable();
    rates.dedup();
    (channels, rates)
}

fn looks_virtual(name: &str) -> bool {
    let lowered = name.to_lowercase();
    ["virtual", "voicemeeter", "vb-audio", "cable", "loopback", "blackhole", "obs"]
        .iter()
        .any(|needle| lowered.contains(needle))
}

fn device_stable_id(kind: &str, name: &str, index: usize) -> String {
    format!("{kind}::{}::{index}", name.replace("::", "_"))
}

fn list_devices_snapshot() -> Result<DeviceSnapshot, String> {
    let (host_id, host) = native_host()?;
    let mut devices = Vec::new();
    for (index, device) in host.devices().map_err(|err| err.to_string())?.enumerate() {
        let name = device.name().unwrap_or_else(|_| "Unknown".to_string());
        if let Ok(configs) = device.supported_input_configs() {
            let (channels, rates) = config_rates(configs);
            devices.push(DeviceInfo {
                id: device_stable_id("input", &name, index),
                name: name.clone(),
                kind: "input".to_string(),
                channels,
                sample_rates: rates,
                virtual_device: looks_virtual(&name),
            });
        }
        if let Ok(configs) = device.supported_output_configs() {
            let (channels, rates) = config_rates(configs);
            devices.push(DeviceInfo {
                id: device_stable_id("output", &name, index),
                name: name.clone(),
                kind: "output".to_string(),
                channels,
                sample_rates: rates,
                virtual_device: looks_virtual(&name),
            });
        }
    }
    Ok(DeviceSnapshot {
        backend: backend_name(host_id),
        devices,
    })
}

fn backend_name(host_id: HostId) -> String {
    format!("{:?}", host_id).to_lowercase()
}

fn list_devices() -> Result<(), String> {
    let snapshot = list_devices_snapshot()?;
    println!("{}", serde_json::to_string_pretty(&snapshot).map_err(|err| err.to_string())?);
    Ok(())
}

fn emit_json(value: Value) -> Result<(), String> {
    let mut stdout = io::stdout().lock();
    serde_json::to_writer(&mut stdout, &value).map_err(|err| err.to_string())?;
    stdout.write_all(b"\n").map_err(|err| err.to_string())?;
    stdout.flush().map_err(|err| err.to_string())?;
    Ok(())
}

fn find_input_device(host: &Host, requested_id: &str) -> Result<(Device, usize, String), String> {
    let devices: Vec<Device> = host.input_devices().map_err(|err| err.to_string())?.collect();
    let requested = requested_id.trim();
    if requested.is_empty() {
        return host
            .default_input_device()
            .map(|device| (device, 0, "default".to_string()))
            .ok_or_else(|| "No default input device available".to_string());
    }
    for (index, device) in devices.into_iter().enumerate() {
        let name = device.name().unwrap_or_else(|_| "Unknown".to_string());
        let stable = device_stable_id("input", &name, index);
        if requested == stable || requested == name || requested == index.to_string() || stable.contains(requested) {
            return Ok((device, index, stable));
        }
    }
    Err(format!("Input device not found: {requested}"))
}

fn choose_input_config(device: &Device, target_rate: u32) -> Result<(StreamConfig, SampleFormat), String> {
    let mut configs: Vec<_> = device.supported_input_configs().map_err(|err| err.to_string())?.collect();
    configs.sort_by_key(|config| {
        let min = config.min_sample_rate().0;
        let max = config.max_sample_rate().0;
        if min <= target_rate && target_rate <= max {
            0
        } else {
            min.abs_diff(target_rate).min(max.abs_diff(target_rate))
        }
    });
    let range = configs.into_iter().next().ok_or_else(|| "No supported input config".to_string())?;
    let selected_rate = if range.min_sample_rate().0 <= target_rate && target_rate <= range.max_sample_rate().0 {
        cpal::SampleRate(target_rate)
    } else {
        range.max_sample_rate()
    };
    let sample_format = range.sample_format();
    Ok((range.with_sample_rate(selected_rate).config(), sample_format))
}

fn start_capture(config: CaptureConfig, event_tx: Sender<CoreEvent>) -> Result<CaptureRuntime, String> {
    let (_, host) = native_host()?;
    let target_rate = config.sample_rate.unwrap_or(16_000).max(8_000);
    let (device, _, stable_id) = find_input_device(&host, &config.device_id)?;
    let device_name = device.name().unwrap_or_else(|_| stable_id.clone());
    let (stream_config, sample_format) = choose_input_config(&device, target_rate)?;
    let input_rate = stream_config.sample_rate.0;
    let input_channels = stream_config.channels.max(1) as usize;
    let stop = Arc::new(AtomicBool::new(false));
    let processor = Arc::new(Mutex::new(CaptureProcessor::new(config, input_rate, input_channels, target_rate)));
    let err_tx = event_tx.clone();
    let err_fn = move |err| {
        let _ = err_tx.send(CoreEvent::Error(format!("Capture stream error: {err}")));
    };

    let stream = match sample_format {
        SampleFormat::F32 => build_input_stream::<f32>(&device, &stream_config, processor, event_tx, err_fn),
        SampleFormat::I16 => build_input_stream::<i16>(&device, &stream_config, processor, event_tx, err_fn),
        SampleFormat::U16 => build_input_stream::<u16>(&device, &stream_config, processor, event_tx, err_fn),
        other => Err(format!("Unsupported sample format: {other:?}")),
    }?;
    stream.play().map_err(|err| err.to_string())?;
    emit_json(json!({
        "event": "capture_started",
        "channel": stable_id,
        "device_name": device_name,
        "input_sample_rate": input_rate,
        "target_sample_rate": target_rate,
        "sample_format": format!("{sample_format:?}")
    }))?;
    Ok(CaptureRuntime { stop, stream })
}

trait InputSample {
    fn to_f32_sample(self) -> f32;
}

impl InputSample for f32 {
    fn to_f32_sample(self) -> f32 {
        self.clamp(-1.0, 1.0)
    }
}

impl InputSample for i16 {
    fn to_f32_sample(self) -> f32 {
        self as f32 / i16::MAX as f32
    }
}

impl InputSample for u16 {
    fn to_f32_sample(self) -> f32 {
        (self as f32 / u16::MAX as f32) * 2.0 - 1.0
    }
}

fn build_input_stream<T>(
    device: &Device,
    config: &StreamConfig,
    processor: Arc<Mutex<CaptureProcessor>>,
    event_tx: Sender<CoreEvent>,
    err_fn: impl FnMut(cpal::StreamError) + Send + 'static,
) -> Result<Stream, String>
where
    T: InputSample + cpal::SizedSample + Send + 'static,
{
    device
        .build_input_stream(
            config,
            move |data: &[T], _| {
                if let Ok(mut guard) = processor.lock() {
                    let events = guard.push_interleaved(data);
                    for event in events {
                        let _ = event_tx.send(event);
                    }
                }
            },
            err_fn,
            None,
        )
        .map_err(|err| err.to_string())
}

struct CaptureProcessor {
    channel: String,
    input_rate: u32,
    input_channels: usize,
    output_rate: u32,
    chunk_samples: usize,
    silence_hold_chunks: u32,
    pre_roll_chunks: usize,
    noise_gate_db: f32,
    input_gain: f32,
    enable_agc: bool,
    agc_target_dbfs: f32,
    max_agc_gain: f32,
    output_buffer: Vec<f32>,
    pre_roll: VecDeque<Vec<i16>>,
    speech_hold_remaining: u32,
    speech_active: bool,
    seq: u64,
    dropped_silent_chunks: u64,
    last_metrics_at: Instant,
    resample_cursor: f64,
}

impl CaptureProcessor {
    fn new(config: CaptureConfig, input_rate: u32, input_channels: usize, output_rate: u32) -> Self {
        let chunk_ms = config.chunk_ms.unwrap_or(20).clamp(10, 120);
        let chunk_samples = ((output_rate as u64 * chunk_ms as u64) / 1000).max(1) as usize;
        let silence_hold_ms = config.silence_hold_ms.unwrap_or(220);
        let silence_hold_chunks = ((silence_hold_ms + chunk_ms - 1) / chunk_ms).max(1);
        let pre_roll_ms = config.pre_roll_ms.unwrap_or(160);
        let pre_roll_chunks = ((pre_roll_ms + chunk_ms - 1) / chunk_ms).max(1) as usize;
        Self {
            channel: config.channel,
            input_rate,
            input_channels: input_channels.max(1),
            output_rate,
            chunk_samples,
            silence_hold_chunks,
            pre_roll_chunks,
            noise_gate_db: config.noise_gate_db.unwrap_or(-48.0),
            input_gain: config.input_gain.unwrap_or(1.0).clamp(0.05, 8.0),
            enable_agc: config.enable_agc.unwrap_or(false),
            agc_target_dbfs: config.agc_target_dbfs.unwrap_or(-18.0),
            max_agc_gain: config.max_agc_gain.unwrap_or(6.0).clamp(1.0, 24.0),
            output_buffer: Vec::with_capacity(chunk_samples * 4),
            pre_roll: VecDeque::new(),
            speech_hold_remaining: 0,
            speech_active: false,
            seq: 0,
            dropped_silent_chunks: 0,
            last_metrics_at: Instant::now(),
            resample_cursor: 0.0,
        }
    }

    fn push_interleaved<T: InputSample + Copy>(&mut self, data: &[T]) -> Vec<CoreEvent> {
        let mono = self.to_mono(data);
        let resampled = self.resample_linear(&mono);
        self.output_buffer.extend(resampled);
        let mut events = Vec::new();
        while self.output_buffer.len() >= self.chunk_samples {
            let chunk: Vec<f32> = self.output_buffer.drain(..self.chunk_samples).collect();
            events.extend(self.process_chunk(&chunk));
        }
        events
    }

    fn to_mono<T: InputSample + Copy>(&self, data: &[T]) -> Vec<f32> {
        let mut mono = Vec::with_capacity(data.len() / self.input_channels + 1);
        for frame in data.chunks(self.input_channels) {
            let sum: f32 = frame.iter().map(|sample| sample.to_f32_sample()).sum();
            mono.push((sum / frame.len().max(1) as f32).clamp(-1.0, 1.0));
        }
        mono
    }

    fn resample_linear(&mut self, input: &[f32]) -> Vec<f32> {
        if input.is_empty() {
            return Vec::new();
        }
        if self.input_rate == self.output_rate {
            return input.to_vec();
        }
        let ratio = self.input_rate as f64 / self.output_rate as f64;
        let mut output = Vec::new();
        while self.resample_cursor < input.len().saturating_sub(1) as f64 {
            let idx = self.resample_cursor.floor() as usize;
            let frac = (self.resample_cursor - idx as f64) as f32;
            let a = input[idx];
            let b = input.get(idx + 1).copied().unwrap_or(a);
            output.push(a + (b - a) * frac);
            self.resample_cursor += ratio;
        }
        self.resample_cursor -= input.len().saturating_sub(1) as f64;
        if self.resample_cursor < 0.0 {
            self.resample_cursor = 0.0;
        }
        output
    }

    fn process_chunk(&mut self, samples: &[f32]) -> Vec<CoreEvent> {
        let level_db = dbfs(samples);
        let speech_now = level_db >= self.noise_gate_db;
        if speech_now {
            self.speech_hold_remaining = self.silence_hold_chunks;
            self.speech_active = true;
        } else if self.speech_hold_remaining > 0 {
            self.speech_hold_remaining -= 1;
            self.speech_active = true;
        } else {
            self.speech_active = false;
        }

        let gain = self.compute_gain(level_db);
        let pcm16 = float_to_pcm16(samples, self.input_gain * gain);
        let mut events = Vec::new();

        if self.speech_active {
            while let Some(pre) = self.pre_roll.pop_front() {
                self.seq += 1;
                events.push(CoreEvent::AudioChunk(AudioChunkEvent {
                    channel: self.channel.clone(),
                    seq: self.seq,
                    sample_rate: self.output_rate,
                    duration_ms: self.chunk_duration_ms(),
                    speech: true,
                    level_db,
                    queue_depth: 0,
                    dropped_silent_chunks: self.dropped_silent_chunks,
                    pcm16: pre,
                }));
            }
            self.seq += 1;
            events.push(CoreEvent::AudioChunk(AudioChunkEvent {
                channel: self.channel.clone(),
                seq: self.seq,
                sample_rate: self.output_rate,
                duration_ms: self.chunk_duration_ms(),
                speech: true,
                level_db,
                queue_depth: 0,
                dropped_silent_chunks: self.dropped_silent_chunks,
                pcm16,
            }));
        } else {
            self.dropped_silent_chunks += 1;
            self.pre_roll.push_back(pcm16);
            while self.pre_roll.len() > self.pre_roll_chunks {
                self.pre_roll.pop_front();
            }
        }

        if self.last_metrics_at.elapsed() >= Duration::from_millis(240) {
            self.last_metrics_at = Instant::now();
            events.push(CoreEvent::Metrics(MetricsEvent {
                channel: self.channel.clone(),
                sample_rate: self.output_rate,
                level_db,
                speech: self.speech_active,
                queue_depth: 0,
                dropped_silent_chunks: self.dropped_silent_chunks,
            }));
        }
        events
    }

    fn compute_gain(&self, level_db: f32) -> f32 {
        if !self.enable_agc || !level_db.is_finite() || level_db < -90.0 {
            return 1.0;
        }
        let delta_db = self.agc_target_dbfs - level_db;
        let gain = 10.0_f32.powf(delta_db / 20.0);
        gain.clamp(0.25, self.max_agc_gain)
    }

    fn chunk_duration_ms(&self) -> u32 {
        ((self.chunk_samples as u64 * 1000) / self.output_rate as u64).max(1) as u32
    }
}

fn dbfs(samples: &[f32]) -> f32 {
    if samples.is_empty() {
        return -96.0;
    }
    let mean_square = samples.iter().map(|sample| sample * sample).sum::<f32>() / samples.len() as f32;
    let rms = mean_square.sqrt().max(1e-6);
    (20.0 * rms.log10()).clamp(-96.0, 6.0)
}

fn float_to_pcm16(samples: &[f32], gain: f32) -> Vec<i16> {
    samples
        .iter()
        .map(|sample| (sample * gain).clamp(-1.0, 1.0))
        .map(|sample| (sample * i16::MAX as f32) as i16)
        .collect()
}

fn write_event(event: CoreEvent) -> Result<(), String> {
    match event {
        CoreEvent::AudioChunk(chunk) => {
            let mut bytes = Vec::with_capacity(chunk.pcm16.len() * 2);
            for sample in chunk.pcm16 {
                bytes.extend_from_slice(&sample.to_le_bytes());
            }
            emit_json(json!({
                "event": "audio_chunk",
                "channel": chunk.channel,
                "seq": chunk.seq,
                "sample_rate": chunk.sample_rate,
                "duration_ms": chunk.duration_ms,
                "speech": chunk.speech,
                "level_db": chunk.level_db,
                "queue_depth": chunk.queue_depth,
                "dropped_silent_chunks": chunk.dropped_silent_chunks,
                "data": BASE64.encode(bytes),
            }))
        }
        CoreEvent::Metrics(metrics) => emit_json(json!({
            "event": "metrics",
            "channel": metrics.channel,
            "sample_rate": metrics.sample_rate,
            "level_db": metrics.level_db,
            "speech": metrics.speech,
            "queue_depth": metrics.queue_depth,
            "dropped_silent_chunks": metrics.dropped_silent_chunks,
        })),
        CoreEvent::Error(message) => emit_json(json!({"event": "error", "message": message})),
    }
}

fn serve() -> Result<(), String> {
    let (host_id, _) = native_host()?;
    emit_json(json!({"event": "ready", "backend": backend_name(host_id)}))?;
    let mut capture: Option<CaptureRuntime> = None;
    let (event_tx, event_rx) = mpsc::channel::<CoreEvent>();
    let (command_tx, command_rx) = mpsc::channel::<Result<Command, String>>();

    thread::spawn(move || {
        let stdin = io::stdin();
        for line in stdin.lock().lines() {
            let command = match line {
                Ok(line) if line.trim().is_empty() => continue,
                Ok(line) => serde_json::from_str(&line).map_err(|err| format!("Invalid command: {err}")),
                Err(err) => Err(err.to_string()),
            };
            if command_tx.send(command).is_err() {
                break;
            }
        }
    });

    loop {
        while let Ok(event) = event_rx.try_recv() {
            write_event(event)?;
        }
        let command = match command_rx.recv_timeout(Duration::from_millis(10)) {
            Ok(command) => command,
            Err(RecvTimeoutError::Timeout) => continue,
            Err(RecvTimeoutError::Disconnected) => break,
        };
        match command {
            Ok(Command::Health) => {
                emit_json(json!({"event": "health", "ok": true, "backend": backend_name(host_id)}))?;
            }
            Ok(Command::ListDevices) => {
                emit_json(json!({"event": "devices", "snapshot": list_devices_snapshot()?}))?;
            }
            Ok(Command::StartCapture(config)) => {
                if let Some(runtime) = capture.take() {
                    runtime.stop.store(true, Ordering::SeqCst);
                    drop(runtime.stream);
                }
                match start_capture(config, event_tx.clone()) {
                    Ok(runtime) => {
                        capture = Some(runtime);
                        emit_json(json!({"event": "ok", "cmd": "start-capture"}))?;
                    }
                    Err(error) => {
                        emit_json(json!({"event": "error", "message": error}))?;
                    }
                }
            }
            Ok(Command::StopCapture) => {
                if let Some(runtime) = capture.take() {
                    runtime.stop.store(true, Ordering::SeqCst);
                    drop(runtime.stream);
                }
                emit_json(json!({"event": "ok", "cmd": "stop-capture"}))?;
            }
            Ok(Command::Shutdown) => {
                if let Some(runtime) = capture.take() {
                    runtime.stop.store(true, Ordering::SeqCst);
                    drop(runtime.stream);
                }
                emit_json(json!({"event": "shutdown"}))?;
                return Ok(());
            }
            Err(error) => {
                emit_json(json!({"event": "error", "message": error}))?;
            }
        }
    }
    if let Some(runtime) = capture.take() {
        runtime.stop.store(true, Ordering::SeqCst);
        drop(runtime.stream);
    }
    Ok(())
}

fn main() {
    let command = std::env::args().nth(1).unwrap_or_else(|| "list-devices".to_string());
    let result = match command.as_str() {
        "list-devices" => list_devices(),
        "serve" => serve(),
        "health" => {
            let (host_id, _) = native_host().map_err(|err| err.to_string()).unwrap();
            println!("{}", json!({"ok": true, "backend": backend_name(host_id)}));
            Ok(())
        }
        _ => Err(format!("Unsupported command: {command}")),
    };

    if let Err(error) = result {
        eprintln!("{error}");
        std::process::exit(1);
    }
}

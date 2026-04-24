use cpal::traits::{DeviceTrait, HostTrait};
use cpal::{HostId, SupportedStreamConfigRange};
use serde::Serialize;

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

fn list_devices() -> Result<(), String> {
    let host = cpal::host_from_id(HostId::Wasapi).map_err(|err| err.to_string())?;
    let mut devices = Vec::new();
    for device in host.devices().map_err(|err| err.to_string())? {
        let name = device.name().unwrap_or_else(|_| "Unknown".to_string());
        let id = format!("{:?}", device);
        if let Ok(configs) = device.supported_input_configs() {
            let (channels, rates) = config_rates(configs);
            devices.push(DeviceInfo {
                id: format!("input::{id}"),
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
                id: format!("output::{id}"),
                name: name.clone(),
                kind: "output".to_string(),
                channels,
                sample_rates: rates,
                virtual_device: looks_virtual(&name),
            });
        }
    }

    let snapshot = DeviceSnapshot {
        backend: "wasapi".to_string(),
        devices,
    };
    println!("{}", serde_json::to_string_pretty(&snapshot).map_err(|err| err.to_string())?);
    Ok(())
}

fn main() {
    let command = std::env::args().nth(1).unwrap_or_else(|| "list-devices".to_string());
    let result = match command.as_str() {
        "list-devices" => list_devices(),
        _ => Err(format!("Unsupported command: {command}")),
    };

    if let Err(error) = result {
        eprintln!("{error}");
        std::process::exit(1);
    }
}

import { useState, useEffect } from "react";
import { Snackbar, IconButton } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";

import "../screens/Settings.css";
import platform from "../platform";
import ThemeToggle from "./ThemeToggle";

type SettingsData = Record<string, Record<string, string | number | boolean>>;

interface SettingsPanelProps {
	onClose?: () => void;
}

/**
 * Reusable settings form — renders fieldsets, action buttons, and snackbar.
 * Used by both the standalone Settings page and the in-call SettingsDrawer.
 */
export default function SettingsPanel({ onClose }: SettingsPanelProps) {
	const [settings, setSettings] = useState<SettingsData | null>(null);
	const [snackbar, setSnackbar] = useState({ open: false, message: "" });

	useEffect(() => {
		platform.getSettings().then((s: SettingsData) => setSettings(s));
	}, []);

	if (!settings) return null; // loading

	// ---------------------------------------------------------------------------
	// Helpers
	// ---------------------------------------------------------------------------

	function updateField(section: string, key: string, value: string | number | boolean) {
		setSettings((prev) => {
			if (!prev) return prev;
			let parsed: string | number | boolean = value;
			if (typeof value === "string" && value !== "") {
				const num = Number(value);
				if (!Number.isNaN(num)) parsed = num;
			}
			return {
				...prev,
				[section]: { ...prev[section], [key]: parsed },
			};
		});
	}

	function toggleField(section: string, key: string) {
		setSettings((prev) => {
			if (!prev) return prev;
			return {
				...prev,
				[section]: { ...prev[section], [key]: !prev[section][key] },
			};
		});
	}

	async function handleSave() {
		if (!settings) return;
		await platform.saveSettings(settings);
		setSnackbar({ open: true, message: "Settings saved. Restart to apply." });
		if (onClose) {
			setTimeout(() => onClose(), 1200);
		}
	}

	async function handleReset() {
		const defaults: SettingsData = await platform.getDefaults();
		setSettings(defaults);
		setSnackbar({ open: true, message: "Defaults restored. Click Save to persist." });
	}

	function handleCancel() {
		if (onClose) onClose();
	}

	// ---------------------------------------------------------------------------
	// Render helpers
	// ---------------------------------------------------------------------------

	function numberInput(section: string, key: string, label: string, step?: string) {
		return (
			<label key={key}>
				<span>{label}</span>
				<input
					type="number"
					step={step || "1"}
					value={settings?.[section]?.[key] as number ?? ""}
					onChange={(e) => updateField(section, key, e.target.value)}
				/>
			</label>
		);
	}

	function selectInput(
		section: string,
		key: string,
		label: string,
		options: string[]
	) {
		return (
			<label key={key}>
				<span>{label}</span>
				<select
					value={String(settings?.[section]?.[key] ?? options[0])}
					onChange={(e) => updateField(section, key, e.target.value)}
				>
					{options.map((opt) => (
						<option key={opt} value={opt}>
							{opt}
						</option>
					))}
				</select>
			</label>
		);
	}

	function checkboxInput(section: string, key: string, label: string, description?: string) {
		const checked = Boolean(settings?.[section]?.[key]);
		return (
			<label key={key} className="checkbox-label">
				<span>
					{label}
					{description && (
						<small className="setting-description">{description}</small>
					)}
				</span>
				<input
					type="checkbox"
					checked={checked}
					onChange={() => toggleField(section, key)}
					className="settings-checkbox"
				/>
			</label>
		);
	}

	return (
		<>
			<fieldset className="settings-group">
				<legend>Appearance</legend>
				<ThemeToggle />
			</fieldset>

			<fieldset className="settings-group">
				<legend>Network</legend>
				{numberInput("network", "electron_ipc_port", "Electron IPC Port")}
				{numberInput("network", "server_rest_port", "Server REST Port")}
				{numberInput("network", "server_websocket_port", "Server WebSocket Port")}
				{numberInput("network", "client_api_port", "Client API Port")}
			</fieldset>

			<fieldset className="settings-group">
				<legend>Video & Audio</legend>
				{numberInput("video", "video_width", "Video Width")}
				{numberInput("video", "video_height", "Video Height")}
				{numberInput("video", "display_width", "Display Width")}
				{numberInput("video", "display_height", "Display Height")}
				{numberInput("video", "frame_rate", "Frame Rate (fps)")}
				{numberInput("audio", "sample_rate", "Sample Rate (Hz)")}
				{numberInput("audio", "audio_wait", "Audio Wait (s)", "0.001")}
				{checkboxInput(
					"audio",
					"mute_by_default",
					"Mute by Default",
					"Start calls with microphone muted."
				)}
			</fieldset>

			<fieldset className="settings-group">
				<legend>Encryption</legend>
				{numberInput("encryption", "key_length", "Key Length (bits)")}
				{selectInput("encryption", "encrypt_scheme", "Encryption Scheme", [
					"AES",
					"XOR",
					"DEBUG",
				])}
				{selectInput("encryption", "key_generator", "Key Generator", [
					"FILE",
					"RANDOM",
					"DEBUG",
				])}
			</fieldset>

			<fieldset className="settings-group">
				<legend>Debug</legend>
				{checkboxInput(
					"debug",
					"video_enabled",
					"Debug Video Mode",
					"Replaces the outgoing camera feed with a loading spinner image."
				)}
			</fieldset>

			<div className="settings-actions">
				<button type="button" onClick={handleSave}>
					Save
				</button>
				<button type="button" onClick={handleReset}>
					Reset to Defaults
				</button>
				<button type="button" id="return-button" onClick={handleCancel}>
					Cancel
				</button>
			</div>

			<p className="settings-note">
				Changes require restarting the application.
			</p>

			<Snackbar
				open={snackbar.open}
				autoHideDuration={4000}
				message={snackbar.message}
				onClose={() => setSnackbar({ ...snackbar, open: false })}
				action={
					<IconButton
						size="small"
						color="inherit"
						onClick={() => setSnackbar({ ...snackbar, open: false })}
					>
						<CloseIcon fontSize="small" />
					</IconButton>
				}
			/>
		</>
	);
}

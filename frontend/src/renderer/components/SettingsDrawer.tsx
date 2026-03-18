import SettingsPanel from "./SettingsPanel";

import "./SettingsDrawer.css";

interface SettingsDrawerProps {
	open: boolean;
	onClose: () => void;
}

/**
 * Right-side slide-out drawer containing the settings form.
 * Used inside the Session screen so users can adjust settings mid-call.
 */
export default function SettingsDrawer({ open, onClose }: SettingsDrawerProps) {
	return (
		<>
			{/* Backdrop — click to close */}
			<div
				className={`settings-drawer-backdrop ${open ? "open" : ""}`}
				onClick={onClose}
			/>

			{/* Drawer panel */}
			<div className={`settings-drawer ${open ? "open" : ""}`}>
				<div className="settings-drawer-header">
					<button
						className="btn btn-icon settings-drawer-close"
						onClick={onClose}
						aria-label="Close settings"
					>
						&#x2715;
					</button>
					<h2>Settings</h2>
				</div>

				<SettingsPanel onClose={onClose} />
			</div>
		</>
	);
}

import { useNavigate } from "react-router-dom";
import Header from "../components/Header";
import SettingsPanel from "../components/SettingsPanel";

import "./Settings.css";

export default function Settings() {
	const navigate = useNavigate();

	return (
		<>
			<Header />
			<div className="settings-content">
				<h2>Settings</h2>
				<SettingsPanel onClose={() => navigate("/start")} />
			</div>
		</>
	);
}

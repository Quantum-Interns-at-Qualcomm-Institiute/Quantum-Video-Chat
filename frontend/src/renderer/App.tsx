import { BrowserRouter as Router, Routes, Route } from "react-router-dom";

import Loading from "./screens/Loading";
import Start from "./screens/Start";
import Join from "./screens/Join";
import Session from "./screens/Session";
import Temp from './screens/Temp';
import { ClientContextProvider } from "./utils/ClientContext";

export default function App() {
	const statuses = ["waiting", "good", "bad"];
	const status = statuses[0];

	return (
		<Router>
			<ClientContextProvider>
				<Routes>
					{/* Host Video Session */}
					<Route
						path="/session/host/*"
						element={<Session host status={status} />}
					/>

					{/* Client Video Session */}
					<Route
						path="/session/client/*"
						element={<Session status={status} />}
					/>

					{/* Join Session Prompt */}
					<Route path="/join" element={<Join />}/>

					<Route path="/temp" element={<Temp/>} />

					{/*  */}
					<Route path="/loading" element={<Loading/>} />

					{/* Home Page */}
					<Route path="/*" element={<Start />}/>
				</Routes>
			</ClientContextProvider>
		</Router>
	);
}

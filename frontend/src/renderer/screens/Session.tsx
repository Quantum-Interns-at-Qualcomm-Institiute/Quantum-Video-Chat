import type { IpcMainEvent } from "electron";
import { useEffect, useState, useRef, useContext } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ClientContext } from "../utils/ClientContext";
import Header from "../components/Header";
import StatusPopup from "../components/StatusPopup";
import VideoPlayer from "../components/VideoPlayer";
import CircleWidget from "../components/widgets/CircleWidget";
import RectangleWidget from "../components/widgets/RectangleWidget";
import Chat from "../components/chat/Chat";

import "./Session.css";

/*
 * props.status: str
 *      - waiting
 *      - bad
 *      - good
 */
export default function Session(props) {
	const canvasRef = useRef(null);
	const client = useContext(ClientContext);

	const location = useLocation();
	const code = location.pathname.slice(-5);

	const [selfSrc, setSelfSrc] = useState(null);
	const [selfSrc2, setSelfSrc2] = useState(null);

	// Start incoming video feed from my camera
	useEffect(() => {
		async function getOutStream() {
			console.log("Session: Attempting to setSelfSrc()");
			const outStream = await navigator.mediaDevices.getUserMedia({
				video: true,
			});
			setSelfSrc(outStream);
			// setSelfSrc2(outStream)
		}
		console.log("Session: Running useEffect()");
		getOutStream();
    const canvas = document.getElementById("peer-stream") as HTMLCanvasElement;
    const context = canvas.getContext("2d") as CanvasRenderingContext2D;
		context.fillStyle = "rgb(255,255,255)";
		context.fillRect(0, 0, canvas.width, canvas.height);
	}, []);

	useEffect(() => {
		window.electronAPI.ipcListen(
			"frame",
			(
				event: IpcMainEvent,
				canvasData: {
					frame: Uint8Array;
					height: number;
					width: number;
				},
			) => {
				const canvas = document.getElementById("peer-stream") as HTMLCanvasElement
				canvas.width = canvasData.width
				canvas.height = canvasData.height
				const context = canvas.getContext("2d") as CanvasRenderingContext2D;
				const imageData = new ImageData(new Uint8ClampedArray(canvasData.frame), canvasData.width, canvasData.height, {colorSpace: 'srgb'})
				context.putImageData(imageData, 0, 0);
			},
		);

		if (props.host) {
			// Is a host
		} else {
			// Is client
			console.log(`sent peer id ${code}`);
			window.electronAPI.setPeerId(code);
		}
	});

	return (
		<>
			<Header status={props.status} />

			{props.status === "bad" ? <StatusPopup /> : null}

			<div className="session-content">
				{/* Add a copy button instead of allowing text selection */}
				<h3 className="code">Code: {client.selfId}</h3>

				<div className="top">
					{/* <div className="video-wrapper" id="left-video"> */}
					{/* Make this come from the backend code so it's the same size*/}
					<canvas id="peer-stream" min-width="640" min-height="480" object-fit="contain"height="auto" width="auto">
						{" "}
						Please wait...{" "}
					</canvas>
					{/* </div> */}
					<div className="vert-spacer" />
					<div className="video-wrapper" id="right-video">
						<VideoPlayer
							srcObject={selfSrc}
							id="self-stream"
							status={props.status}
						/>
					</div>
				</div>

				<div className="bottom">
					<RectangleWidget
						topText="Accumulated Secret Key"
						status={props.status}
					>
						{props.status === "good" ? "# Mbits" : "..."}
					</RectangleWidget>
					<div className="vert-spacer" />
					<CircleWidget
						topText="Key Rate"
						bottomText="Mbits/s"
						status={props.status}
					>
						{props.status === "good" ? "3.33" : "..."}
					</CircleWidget>
					<div className="vert-spacer" />
					<CircleWidget
						topText="Error Rate %"
						bottomText="Mbits"
						status={props.status}
					>
						{props.status === "good" ? "0.2" : "..."}
					</CircleWidget>
					<div className="vert-spacer" />

					<div className="chat-wrapper">
						<Chat
							messages={client.chat.messages}
							handleSend={client.chat.sendMessage}
							status={props.status}
						/>
					</div>

					{/* <button id="quit" onClick={handleQuit}>End Session</button> */}
				</div>
			</div>
		</>
	);
}

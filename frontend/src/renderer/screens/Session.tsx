import type { IpcMainEvent } from "electron";
import { useEffect, useState, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
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

	const location = useLocation();
	const code = location.pathname.slice(-5);

	const [selfSrc, setSelfSrc] = useState(null);
	const [selfSrc2, setSelfSrc2] = useState(null);

	const [messages, setMessages] = useState([
		{
			time: "ti:me",
			name: "Client 1",
			body: "text from client 1",
		},
		{
			time: "ti:me",
			name: "Client 2",
			body: "text from client 2",
		},
	]);

	// TODO: Should instead be defined in another util file (e.g., ../util/API.js)
	function handleChat(message) {
		console.log(`Message Sent: ${message}`);

		const date = new Date();
		const time = date.toLocaleTimeString();
		const messageObj = {
			time: time.substring(0, time.length - 6),
			name: "Client 1",
			body: message,
		};

		setMessages([...messages, messageObj]);
	}

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
		const canvas = document.getElementById("peer-stream");
		const context = canvas?.getContext("2d");
		context.fillstyle = "rgb(255,0,255)";
		context.fillRect(0, 0, canvas.width, canvas.height);
	}, []);

	useEffect(() => {
		window.electronAPI.ipcListen(
			"frame",
			(
				event: IpcMainEvent,
				canvasData: {
					count: number;
					frame: Uint8Array;
					width: number;
					height: number;
					channels: number;
				},
			) => {
				console.log("I've made it to the rendering process!");
				const canvas = document.getElementById("peer-stream");
				const context = canvas.getContext("2d");
				/*
          `image`: An element to draw into the context.
            The specification permits any canvas image source, specifically, an `HTMLImageElement`,
            an `SVGImageElement`, an `HTMLVideoElement`, an `HTMLCanvasElement`, an `ImageBitmap`,
            an `OffscreenCanvas`, or a `VideoFrame`.
          [See: https://developer.mozilla.org/en-US/docs/Web/API/CanvasRenderingContext2D/drawImage]
        */

				const imageData = context.createImageData(
					canvasData.width,
					canvasData.height,
				);

				for (let horiz_pos = 0; horiz_pos < canvasData.width; ++horiz_pos) {
					for (let vert_pos = 0; vert_pos < canvasData.height; ++vert_pos) {
						const pixelIndex = vert_pos * canvasData.width + horiz_pos;

						for (let channel = 0; channel < canvasData.channels; ++channel) {
							imageData.data[pixelIndex * 4 + channel] =
								canvasData.frame[pixelIndex * canvasData.channels + channel];
						}
					}
				}

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
				{code ? <h3 className="code">Code: {code}</h3> : null}

				<div className="top">
					{/* <div className="video-wrapper" id="left-video"> */}
					{/* Make this come from the backend code so it's the same size*/}
					<canvas id="peer-stream" width="640" height="480">
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
							messages={messages}
							handleSend={handleChat}
							status={props.status}
						/>
					</div>

					{/* <button id="quit" onClick={handleQuit}>End Session</button> */}
				</div>
			</div>
		</>
	);
}

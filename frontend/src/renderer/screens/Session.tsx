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

import image from "../../../assets/rando.jpeg";

import "./Session.css";
import { LocalConvenienceStoreOutlined, RateReviewOutlined } from "@mui/icons-material";

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

        // NOTE: Remove all below when ready to test actual frames
        let imageData = document.getElementById("blegh-cringe")
        imageData.addEventListener('load', () => {
            // Resize image for canvas:
            // https://stackoverflow.com/questions/23104582/scaling-an-image-to-fit-on-canvas
            var hRatio = canvas.width / imageData.width;
            var vRatio = canvas.height / imageData.height;
            var ratio = Math.max(hRatio, vRatio);
            context.drawImage(imageData, 0,0, imageData.width, imageData.height, 0, 0, imageData.width*ratio, imageData.height*ratio)
        });
	}, []);

	useEffect(() => {
        client.video.onFrame = (canvasData) => {
            const canvas = document.getElementById("peer-stream") as HTMLCanvasElement
            canvas.width = canvasData.width
            canvas.height = canvasData.height
            const context = canvas.getContext("2d") as CanvasRenderingContext2D;
            const imageData = new ImageData(new Uint8ClampedArray(canvasData.frame), canvasData.width, canvasData.height, {colorSpace: 'srgb'})
            context.putImageData(imageData, 0, 0);
        }
		// window.electronAPI.ipcListen(
		// 	"frame",
		// 	(
		// 		event: IpcMainEvent,
		// 		canvasData: {
		// 			frame: Uint8Array;
		// 			height: number;
		// 			width: number;
		// 		},
		// 	) => {
		// 		const canvas = document.getElementById("peer-stream") as HTMLCanvasElement
		// 		canvas.width = canvasData.width
		// 		canvas.height = canvasData.height
		// 		const context = canvas.getContext("2d") as CanvasRenderingContext2D;
		// 		const imageData = new ImageData(new Uint8ClampedArray(canvasData.frame), canvasData.width, canvasData.height, {colorSpace: 'srgb'})
		// 		context.putImageData(imageData, 0, 0);
		// 	},
		// );
	});


	function handleLeave() {
		client.quitSession();
	}

	return (
		<>
            {/* Remove this after done testing */}
            <div style={{display: "none"}}>
                <img id="blegh-cringe" src={image}></img>
            </div>

			<Header status={props.status} />

			{props.status === "bad" ? <StatusPopup /> : null}

			<div className="session-content">
				{/* Add a copy button instead of allowing text selection */}
				<h3 className="code">ID: {client.selfId}</h3>

				<div className="top">
					{/* <div className="video-wrapper" id="left-video"> */}
					{/* Make this come from the backend code so it's the same size*/}
                    <div className="video-wrapper">
                        <canvas id="peer-stream" object-fit="cover">
                            {" "}
                            Please wait...{" "}
                        </canvas>
                    </div>
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

					{/* 
					<div className="chat-wrapper">
						<Chat
							messages={client.chat.messages}
							handleSend={client.chat.sendMessage}
							status={props.status}
						/>
					</div>
 					*/}

					<button
					className="button leave-button"
					type="button"
					onClick={handleLeave}>
						Leave
					</button>

					{/* <button id="quit" onClick={handleQuit}>End Session</button> */}
				</div>
			</div>
		</>
	);
}

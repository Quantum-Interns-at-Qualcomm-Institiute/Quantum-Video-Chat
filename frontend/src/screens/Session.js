import { useEffect, useState } from "react";
import {useLocation, useNavigate} from "react-router-dom";
import Header from "../components/Header";
import StatusPopup from "../components/StatusPopup";
import VideoPlayer from "../components/VideoPlayer";
import CircleWidget from "../components/widgets/CircleWidget";
import RectangleWidget from "../components/widgets/RectangleWidget";
import Chat from "../components/chat/Chat";

// import { closeSession } from "../util/Auth";
// import {handleChat} from "../util/API.js";

import '../css/Session.css';

/*
 * props.status: str
 *      - waiting
 *      - bad
 *      - good
 */
export default function Session(props) {

    const location = useLocation();
    const code = location.pathname.slice(-8);

    // const startedSession = useRef(false);
    const [selfSrc, setSelfSrc] = useState(null);
    const [selfSrc2, setSelfSrc2] = useState(null);

    const [messages, setMessages] = useState([
        {
            time: "ti:me",
            name: "Client 1",
            body: "text from client 1"
        }, {
            time: "ti:me",
            name: "Client 2",
            body: "text from client 2"
        }
    ]);

    const navigate = useNavigate();

    const handleReturn = () => {
        navigate('/start');
    }

    // TODO: Should instead be defined in another util file (e.g., ../util/API.js)
    function handleChat(message) {
        console.log("Message Sent: " + message);

        var date = new Date();
        const time = date.toLocaleTimeString()
        const messageObj = {
            time: time.substring(0,time.length-6),
            name: "Client 1",
            body: message
        }

        setMessages([...messages, messageObj]);
    }

    // const navigate = useNavigate();

    // const handleQuit = async () => {
    //     await closeSession();
    //     navigate('/');
    // }

    // Start incoming video feed from my camera
    useEffect(() =>{
        async function getOutStream() {
            console.log('Session: Attempting to setSelfSrc()')
            const outStream = await navigator.mediaDevices.getUserMedia({video: true})
            setSelfSrc(outStream)
            setSelfSrc2(outStream)
        }
        console.log('Session: Running useEffect()')
        getOutStream()
    },[])

    return (
        <>
            <Header status={props.status} />

            {props.status == "bad" ? <StatusPopup/> : null}

            <div className="session-content">
                {/* Add a copy button instead of allowing text selection */}
                { code ? <h3 className="code">Code: {code}</h3> : null}

                <div className="top">
                    <div className="video-wrapper" id="left-video">
                        <VideoPlayer loading={props.status != "good"} srcObject={selfSrc2} id="peer-stream" status={props.status}/>
                    </div>
                    <div className="vert-spacer"></div>
                    <div className="video-wrapper" id="right-video">
                        <VideoPlayer srcObject={selfSrc} id="self-stream" status={props.status}/>
                    </div>
                </div>

                <div className="bottom">

                    <RectangleWidget topText="Accumulated Secret Key" status={props.status}>
                        {props.status == "good" ? "# Mbits" : "..."}
                    </RectangleWidget>
                    <div className="vert-spacer"></div>
                    <CircleWidget topText="Key Rate" bottomText="Mbits/s" status={props.status}>
                        {props.status == "good" ? "3.33" : "..."}
                    </CircleWidget>
                    <div className="vert-spacer"></div>
                    <CircleWidget topText="Error Rate %" bottomText="Mbits" status={props.status}>
                        {props.status == "good" ? "0.2" : "..."}
                    </CircleWidget>
                    <div className="vert-spacer"></div>

                    <div className="chat-wrapper">
                        <Chat messages={messages} handleSend={handleChat} status={props.status}/>
                    </div>

                    {/* <button id="quit" onClick={handleQuit}>End Session</button> */}
                </div>
            </div>
        </>
    )
}
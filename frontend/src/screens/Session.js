import {useNavigate} from "react-router-dom";
import Header from "../components/Header";

import { closeSession } from "../util/Auth";

import '../css/Session.css';

export default function Session() {
    const navigate = useNavigate();

    const handleQuit = async () => {
        await closeSession();
        navigate('/');
    }

    return (
        <>
            <Header />

            <div className="session-content">
                <div className="left">
                    <div className="video-stream" id="incoming-video"></div>
                    <div className="info">
                        <div id="key-accumulation">
                            <span>Accumulated Secret Key</span>
                        </div>
                        <div id="key-rate">
                            <span>Key Rate</span>
                        </div>
                        <div id="error-rate">
                            <span>Error Rate</span>
                        </div>
                    </div>
                </div>
                <div className="right">
                    {/* Video Stream element is a temp placeholder */}
                    <div className="video-stream" id="outgoing-video"></div>
                    <div className="chat">
                        <div className="messages">
                            <div className="message" id="incoming-message">
                                <span>text from client 2</span>
                            </div>
                            <div className="message" id="outgoing-message">
                                <span>text from client 1</span>
                            </div>
                        </div>
                        <form className="typing">
                            <input type="text" name="Message" id="text" placeholder="Message"/>
                            <input type="submit" value="Send" id="send"/>
                        </form>
                    </div>

                    <button id="quit" onClick={handleQuit}>End Session</button>
                </div>
            </div>
        </>
    )
}
import {useNavigate} from "react-router-dom";
import Header from "../components/Header";

import "../css/Start.css"

export default function Start() {
    const navigate = useNavigate();

    const handleStart = () => {
        const code = Math.random().toString().slice(2,10);
        navigate(`/session/host/${code}`);
    }

    const handleJoin = () => {
        navigate('/join');
    }

    return (
        <>
            <Header />
            <div className="start-content">
                <div className="codeForm">
                    {/* TODO: Make these buttons be components instead */}
                    <button onClick={handleStart}>Start Session</button>
                    <button onClick={handleJoin}>Join Session</button>
                </div>
            </div>
        </>
    )
}
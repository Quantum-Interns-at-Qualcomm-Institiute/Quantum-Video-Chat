import { useContext} from 'react';
import { useNavigate } from 'react-router-dom';
import { ClientContext } from '../utils/ClientContext';

import Header from '../components/Header';

import './Start.css';

export default function Start() {
    const navigate = useNavigate();
    const client = useContext(ClientContext)

    const handleStart = () => {
        client.joinRoom();
    };

    const handleJoin = () => {
        navigate('/join');
    };

    return (
        <>
        <Header />
        <div className="start-content">
            <div className="codeForm">
                {/* TODO: Make these buttons be components instead */}
                <button type="button" onClick={handleStart}>Start Session</button>
                <button type="button" onClick={handleJoin}>Join Session</button>
            </div>
        </div>
        </>
    );
}

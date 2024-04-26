import StatusWidget from "./widgets/StatusWidget";
import Logo from "../assets/Logo.png";
// import Waveforms from "../assets/Waveforms.png";

import "../css/Header.css";

/* 
 * props.status: str
 *      - waiting: establishing connection
 *      - good: communicatons secure
 *      - bad:  eavesdropper detected
 */
export default function Header(props) {

    return(
        <div className="header">
            <img src={Logo} alt="UCSD Logo" id="logo" />
            <h1>QKD Video Chat</h1>
            <StatusWidget status={props.status} />
        </div>
    );
}
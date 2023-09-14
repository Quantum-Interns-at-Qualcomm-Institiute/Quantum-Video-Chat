import Logo from "../assets/Logo.png";
// import Waveforms from "../assets/Waveforms.png";

import "../css/Header.css";

export default function Header(props) {

    return(
        <div className="header">
            <img src={Logo} alt="UCSD Logo" id="logo" />
            <h1>QKD Video Chat</h1>
            {props.showWaveforms ? 
            <div className="waveforms">
                {/*<img src={Waveforms} alt="Waveforms" id="waveforms" />*/}
                <p>Waveforms</p>
            </div> : null}
        </div>
    );
}
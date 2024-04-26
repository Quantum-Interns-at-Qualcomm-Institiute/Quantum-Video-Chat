import {useEffect, useRef} from 'react';
import Loading from "../../../assets/Loading Screen Effect.mp4";

import './VideoPlayer.css';

/*
 * props.loading: bool
 * props.srcObject: MediaStream obj
 * props.status: str
 *      - waiting
 *      - bad
 *      - good
 */
export default function VideoPlayer(props) {
    
    const videoRef = useRef(null);

    useEffect(() => {
        let video = videoRef.current;
        if (video) {
            console.log('VideoPlayer: Attempting to set video.srcObject')
            video.srcObject = props.loading ? null : props.srcObject;
        }
    },[props.srcObject, props.status]);

    return (
        <div className={`video-player ${props.status}`}>
            <video ref={videoRef} autoPlay={true} loop={props.loading}>
                {props.loading ? <source src={Loading} type="video/mp4"/> : null}
            </video>
        </div>
    );
}
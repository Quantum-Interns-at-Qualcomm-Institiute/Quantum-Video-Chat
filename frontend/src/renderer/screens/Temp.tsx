import React from 'react';
import './Temp.css'; // import your css file
import type { IpcMainEvent } from 'electron';

export default function Temp(props) {
    // const videoRef = React.useRef();

    // // After the component has mounted, access the video element
    // React.useEffect(() => {
    //     navigator.mediaDevices.getUserMedia({video: true})
    //         .then(stream => {
    //             videoRef.current.srcObject = stream;
    //             videoRef.current.play();
    //         })
    //         .catch(err => console.error("Error accessing camera", err));
    // }, []);
    React.useEffect(() => {
      const canvas = document.getElementById('peer-stream') as HTMLCanvasElement;
      const context = canvas.getContext("2d") as CanvasRenderingContext2D;
      context.fillStyle = "rgb(255, 0 ,0)";
      context.fillRect(0, 0, canvas.width, canvas.height);
    },[]);

    React.useEffect(() => {
      window.electronAPI.ipcListen(
        "frame",
        (
          event: IpcMainEvent,
          canvasData: {
            count: number;
            frame: Uint8Array;
            width: number;
            height: number;
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
    });

    return (
        <div>
            <canvas id="peer-stream"/>
            {/* <video ref={videoRef} width="640" height="480" playsInline muted/> */}
        </div>
    );
};

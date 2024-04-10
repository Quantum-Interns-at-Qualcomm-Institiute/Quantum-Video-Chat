import "../../css/CircleWidget.css";

/* 
 * props.topText: str
 * props.bottomText: str
 * props.children: str
 * props.status: str
 *      - waiting: establishing connection
 *      - good: communicatons secure
 *      - bad:  eavesdropper detected
 */
export default function CircleWidget(props) {

    return(
        <div className="circle-widget">
            <div>{props.topText}</div>
            <div className={`circle ${props.status}`}>{props.children}</div>
            <div>{props.bottomText}</div>
        </div>
    );
}
import './Message.css';

export default function Message(props) {

    if(!props.time || !props.name) return;

    return (
        <div className="message">
            {`[${props.time}]<${props.name}> ${props.children}`}
        </div>
    )
}
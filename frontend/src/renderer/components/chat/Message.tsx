import './Message.css';

interface MessageProps {
    time: string;
    name: string;
    children?: React.ReactNode;
}

export default function Message(props: MessageProps) {

    if (!props.time || !props.name) return;

    return (
        <div className="message">
            {`[${props.time}]<${props.name}> ${props.children}`}
        </div>
    )
}

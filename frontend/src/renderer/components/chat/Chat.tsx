import Message from "./Message";

import "./Chat.css";

/* 
 * props.handleSend: function
 * props.messages: sorted arr
 *      - obj:
 *          - time: str
 *          - name: str
 *          - body: str
 * props.status: str
 *      - waiting: establishing connection
 *      - good: communicatons secure
 *      - bad:  eavesdropper detected
 */
export default function Chat(props) {

    function getMessages() {
        if (!props.messages) return

        return props.messages.map((message, i) => {
            if (!message.time || !message.name) return
            return <Message key={`message-${i}`} time={message.time} name={message.name}>{message.body?message.body:null}</Message>
        });
    }

    function handleSubmit(e) {
        e.preventDefault(); 
        let message = e.target[0].value;
        if(props.handleSend != null) props.handleSend(message)
        e.target[0].value = "";
    }

    return(
        <div className={`chat ${props.status}`}>

            <div className="messages">
                {getMessages()}
            </div>

            <form className="chat-field" onSubmit={handleSubmit}>
                <input type="text" name="Message" id="text" placeholder="Message"/>
                <input type="submit" id="send" name ="submit"/>
            </form>
        </div>
    );
}
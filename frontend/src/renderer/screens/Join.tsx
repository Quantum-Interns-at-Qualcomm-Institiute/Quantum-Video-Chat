import { useState, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { ClientContext } from "../utils/ClientContext";
import services from '../utils/services';

import Header from "../components/Header";
import Toast from "../components/Toast";

import "./Join.css";

export default function Join() {

	const client = useContext(ClientContext);
	const navigate = useNavigate();

	const [roomId, setRoomId] = useState("");
	const [error, setError] = useState({
		open: false,
		message: "An error has occured.",
	});

	function handleFieldChange(e) {
		setRoomId(e.target.value);
	}

	const handleReturn = () => {
		navigate("/start");
	};

	const handleSubmit = async (e) => {
		e.preventDefault();
		const response = services.isValidId(roomId);
		if (!response.ok) {
			setError({
				open: true,
				message: (response.error) ? response.error : 'Please enter a valid room ID.'
			})
		} else {
			client.joinRoom(roomId);
		}
	};

	return (
		<>
			<Header />
			<div className="join-content">
				<form className="room-id-form" onSubmit={handleSubmit}>
					<input
						type="text"
						placeholder="Room ID"
						name="room_id"
						id="room-id"
						onChange={handleFieldChange}
                        autoFocus
					/>
					<button type="submit" className="btn">Connect</button>
					<button className="btn" id="return-button" onClick={handleReturn}>
						Return
					</button>
				</form>
			</div>

			{error.open && (
				<Toast
					message={error.message}
					duration={6000}
					onDismiss={() => setError({ ...error, open: false })}
				/>
			)}
		</>
	);
}

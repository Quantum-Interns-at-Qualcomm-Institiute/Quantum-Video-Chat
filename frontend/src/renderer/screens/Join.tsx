import { useState, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { MemoryRouter as Router, Routes, Route } from "react-router-dom";
import { ClientContext } from "../utils/ClientContext";
import services from '../utils/services';

import Header from "../components/Header";
import { IconButton, Snackbar } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";

import "./Join.css";

export default function Join() {

	const client = useContext(ClientContext);
	const navigate = useNavigate();

	const [code, setCode] = useState("");
	const [error, setError] = useState({
		open: false,
		message: "An error has occured.",
	});

	function handleCodeChange(e) {
		setCode(e.target.value);
	}

	const handleReturn = () => {
		navigate("/start");
	};

	const handleSubmit = async (e) => {
		e.preventDefault();
		const response = services.isValidId(code);
		if (!response.ok) {
			setError({
				open: true,
				message: (response.error) ? response.error : 'Please enter a valid code.'
			})
		} else {
			client.joinPeer(code);
			navigate('/session');
		}
	};

	const handleClose = (e, reason) => {
		if (reason === "clickaway") return;
		setError({ ...error, open: false });
	};

	return (
		<>
			<Header />
			<div className="start-content">
				<form className="codeForm" onSubmit={handleSubmit}>
					<input
						type="text"
						placeholder="Code"
						name="code"
						id="code"
						onChange={handleCodeChange}
					/>
					<button type="submit">Connect</button>
					<button id="return-button" onClick={handleReturn}>
						Return
					</button>
				</form>
			</div>

			<Snackbar
				open={error.open}
				autoHideDuration={6000}
				message={error.message}
				onClose={handleClose}
				action={
					<IconButton
						onClick={() => {
							console.log("closed");
						}}
					>
						<CloseIcon fontSize="small" />
					</IconButton>
				}
			/>
		</>
	);
}

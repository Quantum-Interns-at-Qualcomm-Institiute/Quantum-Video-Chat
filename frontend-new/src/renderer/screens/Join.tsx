import {useState} from "react";
import {useNavigate} from "react-router-dom";
import { MemoryRouter as Router, Routes, Route } from 'react-router-dom';
import Header from "../components/Header";
import { IconButton, Snackbar } from "@mui/material";
import CloseIcon from '@mui/icons-material/Close';

import "./Join.css" // TODO: Make separate css for Join

export default function Join() {
    const isValidCode = async (code: string) => {

        let isDigit = /^\d+$/.test(code);
        if (code === "") return {
            ok: false,
            message: "Please enter a valid code."}
        else if (!isDigit) return {
            ok: false,
            message: "Code may only contain numeric characters."}
        else if (code.length !== 8) return {
            ok: false,
            message: "Code must be strictly 8 characters."}
        else return {ok: true, message: "Valid code."};
    }

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
        navigate('/start');
    }

    const handleSubmit = async (e) => {
        e.preventDefault();
        const response = await isValidCode(code);
        if(response.ok) navigate(`/session/client/${code}`)
        else if (response.message) setError({
        open: true,
        message: response.message})
        else setError({...error, open: true})
    }

    const handleClose = (e, reason) => {
        if(reason === "clickaway") return;
        setError({...error, open: false})
    }

    return (
        <>
            <Header />
            <div className="start-content">
                <form className="codeForm" onSubmit={handleSubmit}>
                    <input type="text" placeholder="Code" name="code" id="code" onChange={handleCodeChange}/>
                    <button type="submit">Connect</button>
                    <button id="return-button" onClick={handleReturn}>Return</button>
                </form>
            </div>


            <Snackbar
                open={error.open}
                autoHideDuration={6000}
                message={error.message}
                onClose={handleClose}
                action={
                  <IconButton onClick={() => {
                    console.log("closed");
                  }}>
                        <CloseIcon fontSize="small" />
                    </IconButton>
                }
                />
        </>
    )
}
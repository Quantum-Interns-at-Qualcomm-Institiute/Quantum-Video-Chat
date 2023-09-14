import {useState} from "react";
import {useNavigate} from "react-router-dom";
import Header from "../components/Header";
import {isValidCode} from "../util/Auth";
import { IconButton, Snackbar } from "@material-ui/core";
import CloseIcon from '@mui/icons-material/Close';

import "../css/Start.css"

export default function Start() {
    const navigate = useNavigate();
    const [code, setCode] = useState("");
    const [error, setError] = useState({
        open: false,
        message: "An error has occured.",
    });

    function handleCodeChange(e) {
        setCode(e.target.value);
    }

    const handleSubmit = async (e) => {
        e.preventDefault();
        const response = await isValidCode(code);
        if(response.ok) navigate(`/session/${code}`)
        else if (response.message) setError({
            open: true,
            message: response.message})
        else setError({...error, open: true})
    }

    const handleClose = (e, reason) =>{
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
                </form>
            </div>

            <Snackbar
                open={error.open}
                autoHideDuration={6000}
                message={error.message}
                onClose={handleClose}
                action={
                    <IconButton size="small" onClick={handleClose}>
                        <CloseIcon fontSize="small" />
                    </IconButton>
                }
            />
        </>
    )
}
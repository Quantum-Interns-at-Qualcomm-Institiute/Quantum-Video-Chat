async function isValidCode(code) {

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

async function closeSession() {
    console.log('Closed session');
    return
}

export {isValidCode, closeSession};
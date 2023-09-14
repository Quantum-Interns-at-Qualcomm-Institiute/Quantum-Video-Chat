import { BrowserRouter as Router, Routes, Route } from "react-router-dom";

import Start from "./screens/Start";
import Session from "./screens/Session";

function App() {
    return (
        <Router>
            <Routes>
                {/* ADD SESSION ROUTE HERE */}
                <Route path="/session/*" element={<Session />}>
                </Route>

                {/* Home Page */}
                <Route path="/*" element={<Start />}>
                </Route>
                
            </Routes>
        </Router>
    );
}

export default App;

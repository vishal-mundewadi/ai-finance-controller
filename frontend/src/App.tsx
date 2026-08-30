import { useState } from "react";
import BootIntro from "./components/BootIntro";
import Dashboard from "./components/Dashboard";

function App() {
  const [booted, setBooted] = useState(false);

  return (
    <>
      {!booted && <BootIntro onComplete={() => setBooted(true)} />}
      {booted && <Dashboard />}
    </>
  );
}

export default App;
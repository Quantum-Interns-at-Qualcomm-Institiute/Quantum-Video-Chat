import MainScreen from './screens/MainScreen';
import { ClientContextProvider } from './utils/ClientContext';

export default function App() {
  return (
    <ClientContextProvider>
      <MainScreen />
    </ClientContextProvider>
  );
}

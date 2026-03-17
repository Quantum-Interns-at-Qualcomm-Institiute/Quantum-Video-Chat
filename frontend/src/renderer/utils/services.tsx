import { getSocket } from './socket';

const services = {
  isValidId,
  joinRoom,
  leaveRoom,
  chat: {
    sendMessage,
  },
};

async function joinRoom(room_id?: string): Promise<any> {
  return new Promise((resolve) => {
    getSocket().emit('join_room', room_id ?? null, (err: any) => resolve(err ?? null));
  });
}

async function leaveRoom(): Promise<void> {
  getSocket().emit('leave_room');
}

function sendMessage(message: string) {
  console.log('(services): sendMessage not yet implemented', message);
}

function isValidId(id: string): { ok: boolean; error?: string } {
  if (id === '')          return { ok: false, error: 'Please enter a valid room ID.' };
  if (!/^[a-zA-Z0-9]+$/.test(id))
                          return { ok: false, error: 'ID must be alphanumeric.' };
  if (id.length !== 5)    return { ok: false, error: 'Code must be strictly 5 characters.' };
  return { ok: true };
}

export default services;

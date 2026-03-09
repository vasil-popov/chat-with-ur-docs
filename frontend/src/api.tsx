// src/api.ts
import { Platform } from 'react-native';

// Dynamically set the API URL based on the platform
const API_BASE_URL = 'http://192.168.1.22:8069'

// This is the function our chat UI will call
export const sendChatMessage = async (userMessage: string) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userMessage }), // Matches your backend!
    });

    if (!response.ok) {
      throw new Error('Network response was not ok');
    }

    const data = await response.json();
    return data; // Returns { role: "assistant", content: "..." }
  } catch (error) {
    console.error("API Error:", error);
    return { role: "assistant", content: "Sorry, I couldn't reach the server." };
  }
};
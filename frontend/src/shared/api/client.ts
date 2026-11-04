import axios from "axios";

const baseURL = import.meta.env.VITE_API_URL as string;
const timeout = Number(import.meta.env.VITE_API_TIMEOUT_MS);

export const apiClient = axios.create({
  baseURL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout,
});

const { VITE_BASE_URL: BASE_URL } = import.meta.env;
const { VITE_API_VERSION: API_VERSION } = import.meta.env;
const { VITE_APP_VERSION: APP_VERSION } = import.meta.env;

const API_URL = `${BASE_URL}/api/${API_VERSION}`;

export { API_URL, API_VERSION, APP_VERSION };


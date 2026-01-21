import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App' // 引入您的遊戲檔案
import './index.css'    // 引入 Tailwind 或全域樣式

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <App />
    </React.StrictMode>,
)

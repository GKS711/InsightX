import React, { useState, useRef, useEffect } from 'react';
import { Share2, Download, RefreshCw, ChevronRight, BarChart2, CheckCircle, AlertTriangle, User, Users, Info } from 'lucide-react';

// --- 遊戲資料 ---
const QUESTIONS = [
    {
        id: 1,
        title: "週末爆量，評論開始出現「等很久」",
        imageText: "週末晚餐客滿",
        imageSrc: "/pictures/G1.jpg",
        scenario: "週六晚餐客滿，現場等候 40–60 分鐘。最近一週 Google 評論出現「出餐慢」字眼變多，但店內也覺得「人手不足才是主因」。",
        options: [
            { id: 'A', text: "出餐流程優化（備料、出菜順序）" },
            { id: 'B', text: "候位體驗提升（資訊透明、安撫）" },
            { id: 'C', text: "尖峰人力調度（兼職、分工）" },
            { id: 'D', text: "菜單減法（縮減品項）" }
        ],
        ideal: ['B', 'A'],
        analysis: {
            customerData: [
                { label: "出餐慢", value: 38, type: "negative" },
                { label: "候位不確定感", value: 22, type: "negative" }
            ],
            internalChoice: [
                { label: "人力調度 (C)", value: 65 },
                { label: "其他", value: 35 }
            ],
            conclusion: "優先做 B + A 能最快降負評；C 是中期解。",
            gap: "多數選 C（人力），顧客其實更在意「可預期」。",
            action: "設「候位預估牌 + QR 等候進度」、尖峰先固定 3 道快出品項。"
        }
    },
    {
        id: 2,
        title: "停車抱怨上升，但其實附近有合作停車場",
        imageText: "停車場指引",
        imageSrc: "/pictures/G2.jpg",
        scenario: "近兩週 Facebook 出現「不好停車」負評，店其實有合作停車場，但顧客好像不知道。",
        options: [
            { id: 'A', text: "停車資訊前置（訂位/地圖圖卡）" },
            { id: 'B', text: "停車補助方案（消費折抵）" },
            { id: 'C', text: "門口引導標示（指示牌、地貼）" },
            { id: 'D', text: "尖峰導引人員（門口指揮）" }
        ],
        ideal: ['A', 'C'],
        analysis: {
            customerData: [
                { label: "找不到/不知道", value: 70, type: "risk" },
                { label: "覺得貴", value: 30, type: "neutral" }
            ],
            internalChoice: [
                { label: "補助方案 (B)", value: 60 },
                { label: "資訊前置 (A)", value: 40 }
            ],
            conclusion: "A + C 低成本、最直接；B 只對「知道停車場但覺得貴」的人有效。",
            gap: "顧客提及率：停車 19%，其中 70% 提到「找不到」。",
            action: "Google 商家新增「停車攻略」+ IG 限動精選「怎麼停」。"
        }
    },
    {
        id: 3,
        title: "價格被說貴，但好評也很多",
        imageText: "餐點價值溝通",
        imageSrc: "/pictures/G3.jpg",
        scenario: "Google 評論出現「好吃但偏貴」，同時也有「份量很足、值得」好評。你要怎麼優先處理？",
        options: [
            { id: 'A', text: "價值溝通（原料/工法可視化）" },
            { id: 'B', text: "平日優惠組合（套餐/加購）" },
            { id: 'C', text: "調整價格結構（降價/入門款）" },
            { id: 'D', text: "服務增值（免費小點/續飲）" }
        ],
        ideal: ['A', 'B'],
        analysis: {
            customerData: [
                { label: "嫌貴", value: 14, type: "negative" },
                { label: "值得/份量足", value: 27, type: "positive" }
            ],
            internalChoice: [
                { label: "調整價格 (C)", value: 55 },
                { label: "價值溝通 (A)", value: 45 }
            ],
            conclusion: "多數是「價值感表達不足」而非真的太貴 → A + B 更穩。",
            gap: "內部直覺常想降價 (C)，但數據顯示產品力是被認可的。",
            action: "菜單旁加「手工窯烤/熟成/產地」短句 + 平日雙人套餐。"
        }
    },
    {
        id: 4,
        title: "服務親切被稱讚，但回覆評論做得很隨便",
        imageText: "評論回覆管理",
        imageSrc: "/pictures/G4.jpg",
        scenario: "你們服務很好，但 Google 評論回覆常是制式「謝謝光臨」。最近有人覺得不被重視。",
        options: [
            { id: 'A', text: "回覆模板升級（分情境）" },
            { id: 'B', text: "負評優先處理 SOP（48hr內）" },
            { id: 'C', text: "回覆加入個人化細節" },
            { id: 'D', text: "鼓勵好評引導（結帳卡片）" }
        ],
        ideal: ['B', 'C'],
        analysis: {
            customerData: [
                { label: "回覆態度提及", value: 8, type: "neutral" },
                { label: "負評情緒強度", value: 85, type: "risk" }
            ],
            internalChoice: [
                { label: "忽略此塊", value: 70 },
                { label: "重視回覆", value: 30 }
            ],
            conclusion: "這是「品牌溫度」問題，對評分影響很大 → B + C 先上。",
            gap: "內部常忽略，但這對潛在客人的觀感影響巨大。",
            action: "InsightX 一鍵產生「可直接貼上的回覆」+ 自動分類提醒。"
        }
    },
    {
        id: 5,
        title: "環境被稱讚，但「蚊蟲」開始出現",
        imageText: "戶外用餐區",
        imageSrc: "/pictures/G5.jpg",
        scenario: "帳篷區氣氛超好，但最近天氣變化，開始有人提到蚊蟲或悶熱。",
        options: [
            { id: 'A', text: "防蚊措施（防蚊燈/液/紗網）" },
            { id: 'B', text: "通風/降溫（風扇/座位配置）" },
            { id: 'C', text: "入座前告知（提醒 + 方案）" },
            { id: 'D', text: "區域分流（怕蚊者優先室內）" }
        ],
        ideal: ['A', 'C'],
        analysis: {
            customerData: [
                { label: "蚊蟲提及", value: 11, type: "risk" },
                { label: "悶熱提及", value: 5, type: "neutral" }
            ],
            internalChoice: [
                { label: "降溫設備 (B)", value: 60 },
                { label: "防蚊 (A)", value: 40 }
            ],
            conclusion: "顧客痛點是「可立即感受的不舒服」→ A + C 成效最快。",
            gap: "負向情緒最高的是蚊蟲，而非單純的熱。",
            action: "每桌備防蚊小物 + 入座詢問偏好（室內/帳篷）。"
        }
    },
    {
        id: 6,
        title: "外送開始做了，但評論變兩極",
        imageText: "外送包裝",
        imageSrc: "/pictures/G6.jpg",
        scenario: "你們開外送後，評論開始出現「到家不脆」「包裝漏醬」。內用仍很好。",
        options: [
            { id: 'A', text: "包裝升級（分隔、透氣孔）" },
            { id: 'B', text: "外送菜單調整（不適合下架）" },
            { id: 'C', text: "出餐流程（放置時間、保溫）" },
            { id: 'D', text: "外送補償（補送、折扣碼）" }
        ],
        ideal: ['A', 'B'],
        analysis: {
            customerData: [
                { label: "外送品質抱怨", value: 23, type: "risk" },
                { label: "內用好評", value: 65, type: "positive" }
            ],
            internalChoice: [
                { label: "補償策略 (D)", value: 50 },
                { label: "包裝改善 (A)", value: 50 }
            ],
            conclusion: "補償治標；真正要降負評需 A + B。",
            gap: "高風險項目。內部傾向事後補償，但顧客要的是當下的品質。",
            action: "設外送專用包材 + 外送版菜單（脆度敏感品項移除）。"
        }
    },
    {
        id: 7,
        title: "新菜上線，評價分歧",
        imageText: "新菜色評價",
        imageSrc: "/pictures/G7.jpg",
        scenario: "新推出「辣味披薩」，有人超愛有人說太辣。你要怎麼處理？",
        options: [
            { id: 'A', text: "辣度分級（小/中/大辣）" },
            { id: 'B', text: "菜單描述優化（標示辣感）" },
            { id: 'C', text: "服務話術（點餐確認接受度）" },
            { id: 'D', text: "直接下架（避免兩極）" }
        ],
        ideal: ['A', 'C'],
        analysis: {
            customerData: [
                { label: "辣度抱怨", value: 9, type: "neutral" },
                { label: "正向情緒", value: 60, type: "positive" }
            ],
            internalChoice: [
                { label: "直接下架 (D)", value: 40 },
                { label: "調整 (A/B/C)", value: 60 }
            ],
            conclusion: "這是「可調整的偏好問題」→ A + C 最能保留營收與好評。",
            gap: "內部容易怕麻煩選 D，但其實這道菜有潛力。",
            action: "點餐 UI 加辣度選擇 + 服務確認話術。"
        }
    },
    {
        id: 8,
        title: "尖峰時段電話一直響，影響前台節奏",
        imageText: "前台忙碌",
        imageSrc: "/pictures/G8.jpg",
        scenario: "晚餐時段訂位電話大量湧入，導致點餐流程被打斷，顧客覺得服務慢。",
        options: [
            { id: 'A', text: "線上訂位/候位（減少電話）" },
            { id: 'B', text: "前台分工（專人接聽/帶位）" },
            { id: 'C', text: "電話自動語音（引導線上）" },
            { id: 'D', text: "訂位規則簡化（固定時段）" }
        ],
        ideal: ['A', 'C'],
        analysis: {
            customerData: [
                { label: "服務慢提及", value: 17, type: "negative" },
                { label: "與帶位相關", value: 80, type: "risk" }
            ],
            internalChoice: [
                { label: "前台分工 (B)", value: 70 },
                { label: "科技輔助 (A/C)", value: 30 }
            ],
            conclusion: "短期 B 可止血，但可持續方案是 A + C。",
            gap: "內部常選 B（靠人撐），但這會增加人力成本且不穩定。",
            action: "桌邊 QR 候位 + 電話語音導流。"
        }
    },
    {
        id: 9,
        title: "你們很紅，但「期待太高」導致落差",
        imageText: "網紅名店排隊",
        imageSrc: "/pictures/G9.jpg",
        scenario: "你們在社群很熱門，新客期待很高。近期評論出現「沒有想像中驚艷」。",
        options: [
            { id: 'A', text: "調整行銷訊息（不過度承諾）" },
            { id: 'B', text: "提升招牌品一致性（SOP）" },
            { id: 'C', text: "用戶教育（強調特色工法）" },
            { id: 'D', text: "新客引導（推薦必點）" }
        ],
        ideal: ['B', 'D'],
        analysis: {
            customerData: [
                { label: "期待落差", value: 10, type: "risk" },
                { label: "產品品質", value: 90, type: "neutral" }
            ],
            internalChoice: [
                { label: "忽略", value: 60 },
                { label: "調整", value: 40 }
            ],
            conclusion: "這是「溝通 + 一致性」問題 → B + D 最直接，A/C 輔助。",
            gap: "期待落差對評分殺傷力大，內部容易忽略。",
            action: "必點榜 + 招牌品 QA 檢核。"
        }
    },
    {
        id: 10,
        title: "團隊士氣與顧客評價同時要顧",
        imageText: "內場廚房壓力",
        imageSrc: "/pictures/G10.jpg",
        scenario: "你想改善出餐速度，但廚房反應壓力已很大。怎麼做才能又快又不傷士氣？",
        options: [
            { id: 'A', text: "流程微調（切分工序）" },
            { id: 'B', text: "KPI 合理化（分時段標準）" },
            { id: 'C', text: "培訓劇本（新人上手）" },
            { id: 'D', text: "激勵機制（服務之星）" }
        ],
        ideal: ['A', 'C'],
        analysis: {
            customerData: [
                { label: "出餐慢提及", value: 35, type: "negative" },
                { label: "員工疲憊", value: "High", type: "risk" }
            ],
            internalChoice: [
                { label: "激勵 (D)", value: 30 },
                { label: "KPI (B)", value: 30 },
                { label: "流程 (A/C)", value: 40 }
            ],
            conclusion: "只推 KPI 會反彈；先用 A + C 打底，再配 B/D。",
            gap: "壓力大時，優化工作流程比給獎金更長效。",
            action: "InsightX 生成「週計畫 + 培訓劇本」+ 分段目標。"
        }
    }
];

const App = () => {
    const [gameState, setGameState] = useState('start'); // start, playing, result
    const [currentQIndex, setCurrentQIndex] = useState(0);
    const [selectedOptions, setSelectedOptions] = useState<string[]>([]);
    const [isAnalyzed, setIsAnalyzed] = useState(false);
    const [score, setScore] = useState(0);
    const [isGenerating, setIsGenerating] = useState(false);
    const resultRef = useRef<HTMLDivElement>(null);

    const currentQ = QUESTIONS[currentQIndex];

    // 動態載入 html2canvas
    useEffect(() => {
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
        script.async = true;
        document.body.appendChild(script);

        return () => {
            if (document.body.contains(script)) {
                document.body.removeChild(script);
            }
        };
    }, []);

    const handleStart = () => {
        setGameState('playing');
        setCurrentQIndex(0);
        setScore(0);
        setIsAnalyzed(false);
        setSelectedOptions([]);
    };

    const toggleOption = (id: string) => {
        if (isAnalyzed) return;
        const maxSelection = currentQ.ideal.length;

        if (selectedOptions.includes(id)) {
            setSelectedOptions(selectedOptions.filter(opt => opt !== id));
        } else {
            if (selectedOptions.length < maxSelection) {
                setSelectedOptions([...selectedOptions, id]);
            }
        }
    };

    const handleAnalyze = () => {
        if (selectedOptions.length === 0) return;

        // 計算分數：選中 Ideal 的選項得 1 分
        let currentScore = 0;
        selectedOptions.forEach(opt => {
            if (currentQ.ideal.includes(opt)) {
                currentScore += 1;
            }
        });
        setScore(prev => prev + currentScore);
        setIsAnalyzed(true);
    };

    const handleNext = () => {
        if (currentQIndex < QUESTIONS.length - 1) {
            setCurrentQIndex(prev => prev + 1);
            setSelectedOptions([]);
            setIsAnalyzed(false);
        } else {
            setGameState('result');
        }
    };

    const getResultInfo = () => {
        // 總分 20 分 (每題 2 個正確選項，共 10 題)
        // 17-20: 洞察大師
        // 8-16: 數據驅動
        // 1-7: 潛力新手
        if (score >= 17) return { title: "洞察大師級店長", color: "text-purple-600", desc: "你擁有極敏銳的數據洞察力，能精準平衡顧客體驗與營運效率！" };
        if (score >= 8) return { title: "數據驅動型店長", color: "text-blue-600", desc: "你善於利用數據輔助決策，若能更深入挖掘顧客潛在需求會更完美。" };
        return { title: "潛力新手店長", color: "text-emerald-600", desc: "你很重視直覺，建議多參考客觀數據與分析，能幫助你做出更穩定的決策。" };
    };

    // --- 改進的分享邏輯 ---
    const handleWebShare = async () => {
        if (!resultRef.current || !(window as any).html2canvas) {
            alert("組件載入中，請稍後再試");
            return;
        }

        setIsGenerating(true);

        try {
            const canvas = await (window as any).html2canvas(resultRef.current, {
                backgroundColor: '#ffffff', // Light mode bg
                scale: 2
            });

            canvas.toBlob(async (blob: any) => {
                if (!blob) {
                    setIsGenerating(false);
                    return;
                }

                const file = new File([blob], "insightx_result.jpg", { type: "image/png" });
                const resultInfo = getResultInfo();
                const shareData = {
                    title: 'InsightX 店長決策模擬',
                    text: `我在 InsightX 店長決策模擬中獲得了「${resultInfo.title}」稱號！(得分: ${score}/20)\n快來挑戰看看你的管理智商！ #InsightX #餐廳經營`,
                    files: [file],
                };

                if (navigator.share && navigator.canShare && navigator.canShare(shareData)) {
                    try {
                        await navigator.share(shareData);
                    } catch (err) {
                        console.log('Share failed or canceled', err);
                    }
                } else {
                    alert("您的裝置不支援直接分享圖片到 App。\n\n系統已自動為您下載圖片，請您手動上傳到 FB/IG 喔！");
                    const link = document.createElement('a');
                    link.download = `InsightX_Result_${new Date().getTime()}.png`;
                    link.href = canvas.toDataURL();
                    link.click();
                }
                setIsGenerating(false);
            }, 'image/png');

        } catch (err) {
            console.error("Generate failed", err);
            setIsGenerating(false);
            alert("圖片生成失敗，請稍後再試");
        }
    };

    // 僅下載圖片
    const downloadImage = async () => {
        if (resultRef.current && (window as any).html2canvas) {
            setIsGenerating(true);
            try {
                const canvas = await (window as any).html2canvas(resultRef.current, {
                    backgroundColor: '#ffffff',
                    scale: 2
                });
                const link = document.createElement('a');
                link.download = `InsightX_Result_${new Date().getTime()}.png`;
                link.href = canvas.toDataURL();
                link.click();
            } catch (err) {
                console.error("Image generation failed", err);
                alert("圖片下載失敗，請嘗試直接截圖！");
            }
            setIsGenerating(false);
        }
    };

    // --- Components ---

    const ProgressBar = ({ label, value, color = "bg-blue-500", type = "normal" }: any) => {
        let barColor = color;
        // Adjust colors for light mode
        if (type === 'negative' || type === 'risk') barColor = 'bg-rose-500';
        if (type === 'positive') barColor = 'bg-emerald-500';

        return (
            <div className="mb-3">
                <div className="flex justify-between text-xs mb-1 text-stone-600 font-medium">
                    <span>{label}</span>
                    <span>{typeof value === 'number' ? `${value}%` : value}</span>
                </div>
                <div className="w-full bg-stone-200 rounded-full h-2.5">
                    <div className={`${barColor} h-2.5 rounded-full transition-all duration-500`} style={{ width: typeof value === 'number' ? `${value}%` : '100%' }}></div>
                </div>
            </div>
        );
    };

    if (gameState === 'start') {
        return (
            <div className="min-h-screen bg-[#fafaf9] text-stone-800 flex flex-col items-center justify-center p-6 relative overflow-hidden font-sans">
                {/* Background Decor */}
                <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10 bg-[#fafaf9]">
                    <div className="absolute -top-[10%] -left-[10%] w-[50%] h-[50%] bg-orange-100/40 rounded-full mix-blend-multiply filter blur-3xl animate-blob"></div>
                    <div className="absolute top-[20%] -right-[10%] w-[40%] h-[40%] bg-pink-100/40 rounded-full mix-blend-multiply filter blur-3xl animate-blob animation-delay-2000"></div>
                </div>

                <div className="z-10 text-center max-w-md w-full bg-white/70 p-8 rounded-3xl border border-white shadow-2xl backdrop-blur-xl">
                    <div className="inline-block p-4 rounded-2xl bg-gradient-to-br from-orange-100 to-pink-100 mb-6 shadow-sm">
                        <BarChart2 className="w-12 h-12 text-orange-600" />
                    </div>
                    <h1 className="text-4xl font-black mb-2 bg-gradient-to-r from-orange-600 to-pink-600 bg-clip-text text-transparent tracking-tight">InsightX</h1>
                    <h2 className="text-xl font-bold text-stone-700 mb-6">店長決策模擬室</h2>
                    <p className="text-stone-500 mb-10 leading-relaxed text-lg">
                        面對 10 個真實餐廳經營難題。<br />
                        你的直覺 vs 顧客數據，差距有多大？
                    </p>
                    <button
                        onClick={handleStart}
                        className="w-full py-4 px-6 bg-gradient-to-r from-orange-500 to-pink-600 hover:from-orange-400 hover:to-pink-500 text-white text-lg font-bold rounded-2xl transition-all transform hover:scale-[1.02] shadow-xl shadow-orange-500/20 flex items-center justify-center gap-2"
                    >
                        開始挑戰 <ChevronRight className="w-5 h-5" />
                    </button>
                    <div className="mt-6 text-xs text-stone-400 font-medium">
                        Powered by InsightX Analysis Engine
                    </div>
                </div>
            </div>
        );
    }

    if (gameState === 'result') {
        const resultInfo = getResultInfo();

        return (
            <div className="min-h-screen bg-[#fafaf9] text-stone-800 flex flex-col items-center p-4 overflow-y-auto font-sans">
                <div className="w-full max-w-md py-8">
                    {/* Result Card to be captured */}
                    <div ref={resultRef} className="bg-white p-8 rounded-3xl border border-stone-100 shadow-2xl mb-8 relative overflow-hidden">
                        {/* Decorative Background */}
                        <div className="absolute top-0 right-0 w-40 h-40 bg-orange-100/50 rounded-full blur-3xl -mr-10 -mt-10"></div>
                        <div className="absolute bottom-0 left-0 w-40 h-40 bg-pink-100/50 rounded-full blur-3xl -ml-10 -mb-10"></div>

                        <div className="relative z-10 text-center">
                            <div className="inline-block px-3 py-1 bg-stone-100 rounded-full text-[10px] uppercase tracking-widest text-stone-500 mb-4 font-bold border border-stone-200">InsightX Analysis Report</div>
                            <h2 className={`text-3xl font-black mb-3 ${resultInfo.color}`}>{resultInfo.title}</h2>
                            <p className="text-stone-500 text-sm mb-8 px-4 font-medium leading-relaxed">{resultInfo.desc}</p>

                            <div className="flex justify-center gap-4 mb-8">
                                <div className="bg-stone-50/80 p-6 rounded-2xl border border-stone-100 w-2/3 shadow-inner">
                                    <div className="text-5xl font-black text-stone-800 mb-1">{score} <span className="text-lg text-stone-400 font-normal">/ 20</span></div>
                                    <div className="text-xs text-stone-500 font-bold uppercase tracking-wide">決策得分</div>
                                </div>
                            </div>

                            <div className="bg-blue-50/60 rounded-2xl p-6 text-left mb-8 border border-blue-100">
                                <h3 className="text-sm font-bold text-blue-900 mb-4 flex items-center gap-2">
                                    <Info className="w-4 h-4 text-blue-500" /> 總體建議
                                </h3>
                                <ul className="text-sm text-blue-800 space-y-3 list-disc list-inside marker:text-blue-300">
                                    <li>多關注「顧客沒說出口」的需求</li>
                                    <li>避免落入「內部直覺」的思考陷阱</li>
                                    <li>數據顯示，流程優化往往比補償更有效</li>
                                </ul>
                            </div>

                            <div className="text-xs text-stone-300 font-medium">Generated by InsightX Decision Simulator</div>
                        </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="grid grid-cols-2 gap-4">
                        {/* 主要分享按鈕 */}
                        <button
                            onClick={handleWebShare}
                            disabled={isGenerating}
                            className="col-span-2 flex items-center justify-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white py-4 rounded-2xl transition-all shadow-xl shadow-blue-500/20 font-bold disabled:opacity-70 text-lg group"
                        >
                            {isGenerating ? (
                                <>生成中...</>
                            ) : (
                                <>
                                    <Share2 className="w-5 h-5 group-hover:scale-110 transition-transform" /> 分享結果卡
                                </>
                            )}
                        </button>

                        <button
                            onClick={downloadImage}
                            disabled={isGenerating}
                            className="flex items-center justify-center gap-2 bg-white hover:bg-stone-50 text-stone-600 border border-stone-200 py-3 rounded-xl transition-colors font-bold text-sm shadow-sm"
                        >
                            <Download className="w-4 h-4" /> 僅下載圖片
                        </button>
                        <button
                            onClick={handleStart}
                            className="flex items-center justify-center gap-2 bg-white hover:bg-stone-50 text-stone-600 border border-stone-200 py-3 rounded-xl transition-colors font-bold text-sm shadow-sm"
                        >
                            <RefreshCw className="w-4 h-4" /> 重新挑戰
                        </button>
                    </div>

                    <div className="mt-8 text-center text-xs text-stone-400">
                        若無法直接喚起 FB/IG APP，請點擊「僅下載圖片」後手動上傳。
                    </div>

                </div>
            </div>
        );
    }

    // --- Playing State ---

    const maxSelection = currentQ.ideal.length; // Expected number of answers

    return (
        <div className="min-h-screen bg-[#fafaf9] text-stone-800 p-4 flex flex-col items-center font-sans">
            {/* Header / Progress */}
            <div className="w-full max-w-md mb-6 flex justify-between items-center py-2">
                <div className="text-orange-600 font-black tracking-tighter text-lg">InsightX</div>
                <div className="px-3 py-1 bg-white rounded-full border border-stone-200 text-stone-500 text-xs font-bold shadow-sm">
                    Q {currentQIndex + 1} / {QUESTIONS.length}
                </div>
            </div>

            <div className="w-full max-w-md flex-1 flex flex-col">
                {/* Scenario Card with Image */}
                <div className="bg-white rounded-3xl overflow-hidden mb-6 shadow-xl shadow-stone-200/50 border border-stone-100 group">
                    <div className="w-full h-40 bg-stone-100 overflow-hidden relative">
                        {/* Using local images */}
                        <img
                            src={currentQ.imageSrc}
                            alt={currentQ.imageText}
                            className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                            onError={(e) => {
                                // Fallback if image fails
                                e.currentTarget.src = `https://placehold.co/600x300/f5f5f4/fb923c?text=${encodeURIComponent(currentQ.imageText)}`;
                            }}
                        />
                        <div className="absolute inset-0 bg-gradient-to-t from-stone-900/60 to-transparent"></div>
                        <div className="absolute bottom-4 left-4 right-4">
                            <h2 className="text-xl font-bold text-white leading-tight shadow-black/50 drop-shadow-md">{currentQ.title}</h2>
                        </div>
                    </div>

                    <div className="p-6">
                        <p className="text-stone-600 leading-relaxed font-medium">{currentQ.scenario}</p>
                    </div>
                </div>

                {/* Instruction Text - Prominent */}
                <div className="mb-4 flex items-center justify-between px-1">
                    <div className="text-sm font-bold text-stone-400 uppercase tracking-wider">Options</div>
                    <div className={`text-sm font-bold px-3 py-1 rounded-full ${isAnalyzed ? 'bg-stone-100 text-stone-500' : 'bg-orange-100 text-orange-700 animate-pulse'}`}>
                        {isAnalyzed ? "分析結果" : `請選擇 ${maxSelection} 個最佳方案`}
                    </div>
                </div>

                {/* Options - Grid Layout */}
                <div className="grid grid-cols-1 gap-3 mb-8">
                    {currentQ.options.map((option) => {
                        const isSelected = selectedOptions.includes(option.id);
                        const isIdeal = isAnalyzed && currentQ.ideal.includes(option.id);
                        const isMissed = isAnalyzed && !isSelected && currentQ.ideal.includes(option.id);

                        let borderClass = "border-stone-200";
                        let bgClass = "bg-white";
                        let textClass = "text-stone-600";
                        let shadowClass = "shadow-sm hover:shadow-md";

                        if (isAnalyzed) {
                            shadowClass = "shadow-none";
                            if (isSelected && isIdeal) {
                                borderClass = "border-emerald-500 ring-1 ring-emerald-500";
                                bgClass = "bg-emerald-50";
                                textClass = "text-emerald-800";
                            } else if (isSelected && !isIdeal) {
                                borderClass = "border-rose-400"; // Selected but wrong
                                bgClass = "bg-rose-50";
                                textClass = "text-rose-800";
                            } else if (isMissed) {
                                borderClass = "border-blue-400 border-dashed"; // Correct but not selected
                                bgClass = "bg-blue-50/50";
                                textClass = "text-blue-600";
                            } else {
                                bgClass = "bg-stone-50 opacity-50"; // Irrelevant options
                            }
                        } else {
                            if (isSelected) {
                                borderClass = "border-orange-500 ring-1 ring-orange-500";
                                bgClass = "bg-orange-50";
                                textClass = "text-orange-800";
                                shadowClass = "shadow-md shadow-orange-500/10";
                            } else {
                                bgClass = "bg-white hover:bg-stone-50";
                            }
                        }

                        return (
                            <button
                                key={option.id}
                                onClick={() => toggleOption(option.id)}
                                disabled={isAnalyzed}
                                className={`text-left p-4 rounded-2xl border-2 ${borderClass} ${bgClass} ${textClass} ${shadowClass} transition-all duration-200 flex items-center gap-4 relative`}
                            >
                                <div className={`w-8 h-8 rounded-full border-2 flex items-center justify-center flex-shrink-0 font-bold transition-colors ${isSelected || (isAnalyzed && isIdeal)
                                    ? 'border-current bg-current text-white'
                                    : 'border-stone-200 text-stone-400 bg-white'
                                    }`}>
                                    {isSelected || (isAnalyzed && isIdeal) ? (isAnalyzed && isIdeal ? <CheckCircle className="w-5 h-5" /> : <span className="text-sm">{option.id}</span>) : <span className="text-sm">{option.id}</span>}
                                </div>
                                <span className="text-base font-bold leading-tight">{option.text}</span>

                                {isAnalyzed && isMissed && <span className="absolute right-4 text-xs font-bold text-blue-500 bg-blue-100 px-2 py-1 rounded">這是正解</span>}
                            </button>
                        );
                    })}
                </div>

                {/* Analysis Section (Shows after confirm) */}
                {isAnalyzed && (
                    <div className="bg-white rounded-3xl p-6 mb-24 animate-in fade-in slide-in-from-bottom-4 duration-500 border border-stone-200 shadow-2xl shadow-stone-200/50">
                        <div className="flex items-center gap-3 mb-6 border-b border-stone-100 pb-4">
                            <div className="p-2 bg-blue-50 rounded-xl">
                                <BarChart2 className="w-5 h-5 text-blue-600" />
                            </div>
                            <h3 className="font-bold text-stone-800 text-lg">InsightX 分析結論</h3>
                        </div>

                        <div className="grid grid-cols-2 gap-4 mb-6">
                            <div className="bg-stone-50 p-4 rounded-2xl border border-stone-100">
                                <div className="flex items-center gap-1 text-xs font-bold text-stone-400 mb-3 uppercase tracking-wider">
                                    <Users className="w-3 h-3" /> 顧客提及率
                                </div>
                                {currentQ.analysis.customerData.map((d, i) => (
                                    <ProgressBar key={i} {...d} />
                                ))}
                            </div>
                            <div className="bg-stone-50 p-4 rounded-2xl border border-stone-100">
                                <div className="flex items-center gap-1 text-xs font-bold text-stone-400 mb-3 uppercase tracking-wider">
                                    <User className="w-3 h-3" /> 內部選擇分布
                                </div>
                                {currentQ.analysis.internalChoice.map((d, i) => (
                                    <ProgressBar key={i} {...d} color="bg-purple-500" />
                                ))}
                            </div>
                        </div>

                        <div className="space-y-4 text-sm bg-orange-50/50 p-5 rounded-2xl border border-orange-100/50">
                            <div className="flex gap-3 items-start">
                                <AlertTriangle className="w-5 h-5 text-orange-500 mt-0.5 flex-shrink-0" />
                                <div>
                                    <span className="text-orange-700 font-bold block mb-1 text-base">落差結論</span>
                                    <span className="text-stone-600 leading-relaxed block">{currentQ.analysis.gap}</span>
                                </div>
                            </div>
                            <div className="w-full h-px bg-orange-200/50 my-2"></div>
                            <div className="flex gap-3 items-start">
                                <CheckCircle className="w-5 h-5 text-emerald-500 mt-0.5 flex-shrink-0" />
                                <div>
                                    <span className="text-emerald-700 font-bold block mb-1 text-base">建議行動</span>
                                    <span className="text-stone-600 leading-relaxed block">{currentQ.analysis.action}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Footer Action Button */}
            <div className="fixed bottom-0 left-0 w-full p-4 bg-white/80 backdrop-blur-md border-t border-stone-200 flex justify-center z-50">
                <div className="w-full max-w-md">
                    {!isAnalyzed ? (
                        <button
                            onClick={handleAnalyze}
                            disabled={selectedOptions.length === 0}
                            className="w-full py-4 bg-stone-900 hover:bg-stone-800 disabled:bg-stone-200 disabled:text-stone-400 text-white text-lg font-bold rounded-2xl transition-all shadow-xl shadow-stone-900/10 flex items-center justify-center"
                        >
                            確認並分析
                        </button>
                    ) : (
                        <button
                            onClick={handleNext}
                            className="w-full py-4 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white text-lg font-bold rounded-2xl transition-all flex items-center justify-center gap-2 shadow-xl shadow-emerald-500/20"
                        >
                            {currentQIndex < QUESTIONS.length - 1 ? "下一題" : "查看最終結果"} <ChevronRight className="w-5 h-5" />
                        </button>
                    )}
                </div>
            </div>

            {/* Spacer for fixed footer */}
            <div className="h-24"></div>
        </div>
    );
};

export default App;
"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { Send, User, Bot, Copy, Check, AlertCircle, Loader2 } from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

const SAMPLE_QUESTIONS = [
    "Boşanma davalarında yetkili mahkeme neresidir?",
    "Kıdem tazminatına hak kazanmanın şartları nelerdir?",
    "İşveren haksız yere işten çıkarırsa haklarım nelerdir?",
    "Kiracı kirayı ödemezse tahliye süreci nasıl işler?",
    "Anlaşmalı boşanma davası ne kadar sürer?",
    "Tüketici hakem heyetine nasıl başvurulur?",
    "Miras paylaşımında saklı pay nedir?",
    "Mobbing (psikolojik taciz) durumunda haklarım nelerdir?",
    "Nafaka ödenmemesi durumunda ne yapabilirim?",
    "Kötü niyetli tazminat davası nasıl açılır?"
];

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    isError?: boolean;
    isTyping?: boolean;
}

interface ChatInterfaceProps {
    conversationId: string | null;
    onConversationCreated: (id: string) => void;
}

function getAuthHeaders(): Record<string, string> {
    return {
        "x-user-id": "local_user",
        "x-user-email": "local@user.com",
    };
}

export default function ChatInterface({ conversationId, onConversationCreated }: ChatInterfaceProps) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [copiedId, setCopiedId] = useState<string | null>(null);
    const [suggestions, setSuggestions] = useState<string[]>([]);
    const [loadingHistory, setLoadingHistory] = useState(false);

    const messagesEndRef = useRef<HTMLDivElement>(null);
    const currentConvIdRef = useRef<string | null>(conversationId);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    useEffect(() => {
        const shuffled = [...SAMPLE_QUESTIONS].sort(() => 0.5 - Math.random());
        setSuggestions(shuffled.slice(0, 2));
    }, []);

    // Load messages when conversationId changes
    useEffect(() => {
        currentConvIdRef.current = conversationId;

        if (!conversationId) {
            setMessages([]);
            return;
        }

        const loadMessages = async () => {
            setLoadingHistory(true);
            try {
                const res = await fetch(`/api/conversations/${conversationId}/messages`, {
                    headers: getAuthHeaders(),
                });
                if (res.ok) {
                    const data = await res.json();
                    setMessages(
                        data.map((m: any) => ({
                            id: m.id,
                            role: m.role,
                            content: m.content,
                        }))
                    );
                }
            } catch (err) {
                console.error("Failed to load messages:", err);
            } finally {
                setLoadingHistory(false);
            }
        };

        loadMessages();
    }, [conversationId]);

    const saveMessage = useCallback(
        async (convId: string, role: string, content: string) => {
            try {
                await fetch(`/api/conversations/${convId}/messages`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        ...getAuthHeaders(),
                    },
                    body: JSON.stringify({ conversation_id: convId, role, content }),
                });
            } catch (err) {
                console.error("Failed to save message:", err);
            }
        },
        []
    );

    const createConversation = useCallback(
        async (title: string): Promise<string | null> => {
            try {
                const res = await fetch("/api/conversations", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        ...getAuthHeaders(),
                    },
                    body: JSON.stringify({ title }),
                });
                if (res.ok) {
                    const data = await res.json();
                    return data.id;
                }
            } catch (err) {
                console.error("Failed to create conversation:", err);
            }
            return null;
        },
        []
    );

    const handleCopy = async (id: string, content: string) => {
        try {
            await navigator.clipboard.writeText(content);
            setCopiedId(id);
            setTimeout(() => setCopiedId(null), 2000);
        } catch (err) {
            console.error("Metin kopyalanamadı: ", err);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isLoading) return;

        const userQuery = input.trim();
        setInput("");

        const userMsgId = Date.now().toString();
        const assistantMsgId = (Date.now() + 1).toString();

        setMessages((prev) => [
            ...prev,
            { id: userMsgId, role: "user", content: userQuery }
        ]);

        setIsLoading(true);

        // Add dummy typing indicator message
        setMessages((prev) => [
            ...prev,
            { id: assistantMsgId, role: "assistant", content: "", isTyping: true }
        ]);

        // Create conversation if this is the first message
        let convId = currentConvIdRef.current;
        if (!convId) {
            const title = userQuery.length > 50 ? userQuery.substring(0, 50) + "..." : userQuery;
            convId = await createConversation(title);
            if (convId) {
                currentConvIdRef.current = convId;
                onConversationCreated(convId);
            }
        }

        // Save user message
        if (convId) {
            saveMessage(convId, "user", userQuery);
        }

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...getAuthHeaders(),
                },
                body: JSON.stringify({ query: userQuery, conversation_id: convId }),
            });

            if (!response.ok) {
                throw new Error("Backend response error");
            }

            const reader = response.body?.getReader();
            if (!reader) throw new Error("No reader");

            const decoder = new TextDecoder("utf-8");

            // Remove typing indicator initially before starting stream parsing
            setMessages((prev) =>
                prev.map((msg) =>
                    msg.id === assistantMsgId
                        ? { ...msg, isTyping: false, content: "" }
                        : msg
                )
            );

            let done = false;
            let currentAssistantContent = "";

            while (!done) {
                const { value, done: doneReading } = await reader.read();
                done = doneReading;
                if (value) {
                    const chunkStr = decoder.decode(value, { stream: true });
                    const lines = chunkStr.split("\n");
                    for (const line of lines) {
                        if (line.startsWith("data: ")) {
                            try {
                                const dataStr = line.substring(6);
                                const data = JSON.parse(dataStr);
                                
                                if (data.type === "token") {
                                    currentAssistantContent += data.token;
                                    setMessages((prev) =>
                                        prev.map((msg) =>
                                            msg.id === assistantMsgId
                                                ? { ...msg, content: currentAssistantContent }
                                                : msg
                                        )
                                    );
                                } else if (data.type === "final") {
                                    const finalContent = data.data.answer || currentAssistantContent;
                                    setMessages((prev) =>
                                        prev.map((msg) =>
                                            msg.id === assistantMsgId
                                                ? { ...msg, content: finalContent }
                                                : msg
                                        )
                                    );
                                    // Save assistant message
                                    if (convId) {
                                        saveMessage(convId, "assistant", finalContent);
                                    }
                                } else if (data.type === "error") {
                                    setMessages((prev) =>
                                        prev.map((msg) =>
                                            msg.id === assistantMsgId
                                                ? { ...msg, isError: true }
                                                : msg
                                        )
                                    );
                                } else if (data.type === "done") {
                                    done = true;
                                }
                            } catch (e) {
                                console.error("Error parsing SSE line:", e);
                            }
                        }
                    }
                }
            }
        } catch (error) {
            console.error("Chat backend connection error:", error);
            setMessages((prev) =>
                prev.map((msg) =>
                    msg.id === assistantMsgId
                        ? { ...msg, isTyping: false, isError: true, content: "Bağlantı hatası oluştu. Lütfen backend sunucusunun çalışıp çalışmadığını kontrol edin." }
                        : msg
                )
            );
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex flex-col w-full h-[calc(100vh-8rem)] bg-card border border-border rounded-2xl shadow-xl overflow-hidden relative">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-card/80 backdrop-blur top-0 z-10">
                <div className="flex items-center space-x-3">
                    <div className="h-10 w-10 flex items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
                        <Bot size={24} className="stroke-[1.5]" />
                    </div>
                    <div>
                        <h2 className="text-xl font-semibold tracking-tight text-foreground">Asistan</h2>
                        <p className="text-xs text-muted-foreground font-medium">Hukuk RAG Sohbet Robotu</p>
                    </div>
                </div>
            </div>

            {/* Chat Area */}
            <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-8 scroll-smooth bg-muted/10">
                {loadingHistory ? (
                    <div className="h-full flex items-center justify-center">
                        <div className="flex flex-col items-center gap-3">
                            <Loader2 className="w-6 h-6 animate-spin text-primary" />
                            <p className="text-sm text-muted-foreground">Sohbet yükleniyor...</p>
                        </div>
                    </div>
                ) : messages.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-center space-y-6 px-4 animate-in fade-in duration-500">
                        <div className="h-20 w-20 flex items-center justify-center rounded-2xl bg-primary/10 text-primary mb-4 p-4 shadow-inner border border-primary/20">
                            <Bot className="w-full h-full stroke-[1.5]" />
                        </div>
                        <div className="space-y-2">
                            <h2 className="text-2xl font-semibold tracking-tight text-foreground">Size nasıl yardımcı olabilirim?</h2>
                            <p className="text-muted-foreground max-w-md mx-auto leading-relaxed">
                                Hukuki metinler, içtihatlar ve mevzuat hakkında sorular sorabilirsiniz. Çıktılar kanun maddeleri ile desteklenecektir.
                            </p>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-2xl mt-8">
                            {suggestions.map((suggestion, i) => (
                                <button
                                    key={i}
                                    onClick={() => setInput(suggestion)}
                                    className="text-left p-4 rounded-xl border border-border bg-card hover:border-primary/50 hover:shadow-md transition-all duration-200 text-sm font-medium text-foreground/80 hover:text-primary"
                                >
                                    {suggestion}
                                </button>
                            ))}
                        </div>
                    </div>
                ) : (
                    messages.map((msg) => (
                        <div
                            key={msg.id}
                            className={cn(
                                "flex w-full animate-in slide-in-from-bottom-2 fade-in duration-300",
                                msg.role === "user" ? "justify-end" : "justify-start"
                            )}
                        >
                            <div
                                className={cn(
                                    "flex max-w-[85%] md:max-w-[75%] gap-4",
                                    msg.role === "user" ? "flex-row-reverse" : "flex-row"
                                )}
                            >
                                {/* Avatar */}
                                <div
                                    className={cn(
                                        "flex-shrink-0 h-10 w-10 rounded-full flex items-center justify-center mt-1 border shadow-sm",
                                        msg.role === "user"
                                            ? "bg-secondary border-border"
                                            : "bg-primary text-primary-foreground border-transparent"
                                    )}
                                >
                                    {msg.role === "user" ? <User size={18} /> : <Bot size={18} />}
                                </div>

                                {/* Message Bubble */}
                                <div
                                    className={cn(
                                        "flex flex-col space-y-2 text-sm",
                                        msg.role === "user" ? "items-end" : "items-start"
                                    )}
                                >
                                    <div
                                        className={cn(
                                            "px-5 py-4 rounded-3xl shadow-sm whitespace-pre-wrap leading-relaxed text-[15px]",
                                            msg.role === "user"
                                                ? "bg-primary text-primary-foreground rounded-tr-md"
                                                : "bg-card border border-border text-foreground rounded-tl-md",
                                            msg.isError && "border-destructive/50 bg-destructive/10 text-destructive-foreground dark:text-red-400"
                                        )}
                                    >
                                        {msg.isTyping ? (
                                            <div className="flex space-x-1.5 items-center h-5 px-1 py-1">
                                                <div className="w-2 h-2 bg-primary/60 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                                <div className="w-2 h-2 bg-primary/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                                <div className="w-2 h-2 bg-primary/60 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                            </div>
                                        ) : (
                                            msg.content
                                        )}

                                        {msg.isError && (
                                            <div className="flex items-center space-x-2 mt-2 text-destructive text-xs font-medium">
                                                <AlertCircle size={14} />
                                                <span>Bir hata meydana geldi.</span>
                                            </div>
                                        )}
                                    </div>

                                    {/* Actions */}
                                    {msg.role === "assistant" && !msg.isTyping && msg.content && (
                                        <div className="flex flex-col space-y-3 mt-2 w-full pl-2">
                                            <div className="flex items-center space-x-2">
                                                <button
                                                    onClick={() => handleCopy(msg.id, msg.content)}
                                                    className="flex items-center space-x-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors py-1.5 px-3 rounded-lg hover:bg-secondary border border-transparent hover:border-border"
                                                >
                                                    {copiedId === msg.id ? (
                                                        <>
                                                            <Check size={14} className="text-green-500" />
                                                            <span className="text-green-500">Kopyalandı</span>
                                                        </>
                                                    ) : (
                                                        <>
                                                            <Copy size={14} />
                                                            <span>Kopyala</span>
                                                        </>
                                                    )}
                                                </button>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))
                )}
                <div ref={messagesEndRef} className="h-4" />
            </div>

            {/* Input Area */}
            <div className="p-4 bg-card border-t border-border z-10 w-full shadow-[0_-10px_40px_-15px_rgba(0,0,0,0.05)]">
                <form
                    onSubmit={handleSubmit}
                    className="relative flex items-end w-full max-w-4xl mx-auto rounded-2xl bg-background border border-border focus-within:ring-2 focus-within:ring-primary/40 focus-within:border-primary/50 transition-all shadow-sm"
                >
                    <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                handleSubmit(e);
                            }
                        }}
                        disabled={isLoading}
                        placeholder={isLoading ? "Yapay zeka yanıtlıyor..." : "Hukuki sorunuzu yazın (Göndermek için Enter'a basın)..."}
                        className="w-full min-h-[60px] max-h-[160px] pl-6 pr-16 py-4 rounded-2xl bg-transparent text-foreground placeholder-muted-foreground focus:outline-none resize-none text-[15px] leading-relaxed disabled:opacity-50 disabled:cursor-not-allowed"
                        rows={1}
                    />
                    <div className="absolute right-3 bottom-3 flex items-center">
                        <button
                            type="submit"
                            disabled={!input.trim() || isLoading}
                            className="p-2.5 bg-primary text-primary-foreground rounded-xl transition-all hover:bg-primary/90 disabled:opacity-40 disabled:hover:scale-100 hover:scale-105 active:scale-95 flex items-center justify-center shadow-md disabled:shadow-none disabled:cursor-not-allowed"
                        >
                            <Send size={18} className={cn("transition-transform", input.trim() && !isLoading ? "translate-x-0.5 -translate-y-0.5" : "")} />
                        </button>
                    </div>
                </form>
                <div className="text-center mt-4">
                    <p className="text-[11px] text-muted-foreground font-medium">
                        Hukuk AI bir asistan sistemidir. Aldığınız cevaplar yasal danışmanlık yerine geçmez ve hukuk profesyonelleri tarafından teyit edilmelidir.
                    </p>
                </div>
            </div>
        </div>
    );
}

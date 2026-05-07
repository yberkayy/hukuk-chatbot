"use client";

import { useState, useCallback } from "react";
import ChatInterface from "@/components/chat-interface";
import ChatSidebar from "@/components/chat-sidebar";
import {
  MessageSquare,
  Scale,
  Menu,
} from "lucide-react";

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleNewChat = useCallback(() => {
    setActiveConversationId(null);
  }, []);

  const handleSelectConversation = useCallback((id: string) => {
    setActiveConversationId(id);
  }, []);

  const handleConversationCreated = useCallback((id: string) => {
    setActiveConversationId(id);
    setRefreshTrigger((prev) => prev + 1);
  }, []);



  return (
    <div className="min-h-screen flex bg-background text-foreground bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-100 via-background to-background dark:from-slate-900">
      {/* Sidebar */}
      <ChatSidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
        onNewChat={handleNewChat}
        refreshTrigger={refreshTrigger}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Navigation Bar */}
        <header className="bg-card border-b border-border px-4 py-3 flex items-center justify-between sticky top-0 z-30 shadow-sm gap-4">
          {/* Left: Hamburger + Title */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 rounded-lg hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors"
              title="Sohbet geçmişi"
            >
              <Menu size={20} />
            </button>
            <div className="flex items-center gap-3">
              <div className="bg-primary/10 p-2 rounded-lg">
                <Scale className="w-5 h-5 text-primary" />
              </div>
              <div className="hidden sm:block">
                <h1 className="text-lg font-bold tracking-tight text-card-foreground">
                  Yapay Zeka Hukuk Asistanı
                </h1>
                <p className="text-xs text-muted-foreground">
                  Bu platform,<a href="https://mevzuat.gov.tr" target="_blank" > <u>mevzuat.gov.tr</u></a>'den alınan yasaları OpenAI API ve vektör tabanlı arama ile işleyerek, kullanıcıların olaylarına uygun bilgilendirici yorumlar sunar. Sistem tamamen EĞİTİM ve farkındalık amaçlıdır, hukuki danışmanlık sağlamaz.
                </p>
              </div>
            </div>
          </div>



          <div className="flex items-center gap-3">
          </div>
        </header>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col overflow-y-auto lg:overflow-hidden relative">
          <div className="flex-1 h-full w-full max-w-7xl mx-auto p-3 sm:p-4 md:p-6 transition-opacity duration-300">
            <div className="h-full flex flex-col animate-in fade-in slide-in-from-bottom-4 duration-500">
              <ChatInterface
                conversationId={activeConversationId}
                onConversationCreated={handleConversationCreated}
              />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

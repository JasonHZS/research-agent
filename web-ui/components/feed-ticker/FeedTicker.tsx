'use client';

import { useEffect, useRef, useState } from 'react';
import { useAuth } from '@clerk/nextjs';
import { GripVertical } from 'lucide-react';
import { getApiBaseUrl } from '@/lib/utils';
import type { FeedDigestItem, FeedDigestResponse } from '@/lib/types';

function parseFeedDate(value: string): Date | null {
  const direct = new Date(value);
  if (!Number.isNaN(direct.getTime())) {
    return direct;
  }

  const legacy = value.match(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/)
    ? new Date(`${value.replace(' ', 'T')}:00Z`)
    : null;
  if (!legacy || Number.isNaN(legacy.getTime())) {
    return null;
  }
  return legacy;
}

function FeedCard({ item, lang }: { item: FeedDigestItem; lang: 'zh' | 'en' }) {
  const parsedDate = item.latest_date ? parseFeedDate(item.latest_date) : null;
  const formattedDate = parsedDate
    ? parsedDate.toLocaleDateString('zh-CN', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    : '';

  const title =
    lang === 'zh'
      ? (item.latest_title_zh ?? item.latest_title)
      : item.latest_title;
  const summary =
    lang === 'zh'
      ? (item.latest_summary_zh ?? item.latest_summary)
      : item.latest_summary;

  return (
    <a
      href={item.latest_url ?? '#'}
      target="_blank"
      rel="noopener noreferrer"
      draggable={true}
      onDragStart={(e) => {
        e.dataTransfer.clearData();
        e.dataTransfer.setData('application/feed-card', JSON.stringify(item));
        e.dataTransfer.effectAllowed = 'copy';
      }}
      className="group relative flex h-[96px] w-[360px] flex-shrink-0 flex-col justify-between overflow-hidden rounded-xl border border-border bg-card/80 px-3.5 py-2.5 shadow-sm backdrop-blur transition-colors hover:border-orange-500/30 hover:bg-orange-500/5"
    >
      {/* Drag handle indicator */}
      <div className="absolute right-2 top-2 opacity-0 transition-opacity group-hover:opacity-100">
        <GripVertical className="h-3.5 w-3.5 text-muted-foreground/40" />
      </div>
      {/* 上部：标题 + 摘要 */}
      <div className="flex flex-col gap-1">
        <span className="line-clamp-1 text-[12px] font-semibold leading-snug text-foreground group-hover:text-orange-600 dark:group-hover:text-orange-400">
          {title}
        </span>
        {summary && (
          <span className="line-clamp-2 text-[11px] leading-relaxed text-muted-foreground/80">
            {summary}
          </span>
        )}
      </div>
      {/* 下部：博客名 + 日期 */}
      <div className="flex items-center justify-end gap-2">
        <span className="truncate text-[10px] text-muted-foreground/50">
          {item.feed_name}
        </span>
        {formattedDate && (
          <span className="flex-shrink-0 text-[10px] text-muted-foreground/40">
            {formattedDate}
          </span>
        )}
      </div>
    </a>
  );
}

export function FeedTicker() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [items, setItems] = useState<FeedDigestItem[]>([]);
  const [lang, setLang] = useState<'zh' | 'en'>('zh');
  const scrollRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number>(0);
  const pauseUntilRef = useRef<number>(0);
  const dragging = useRef(false);
  const dragStartX = useRef(0);
  const dragScrollLeft = useRef(0);
  const hasDragged = useRef(false);

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;

    let cancelled = false;

    const loadDigest = async () => {
      try {
        const token = await getToken();
        if (!token) return;

        const baseUrl = getApiBaseUrl();
        const response = await fetch(`${baseUrl}/api/feeds/digest`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        if (!response.ok) {
          throw new Error(`${response.status} ${response.statusText}`);
        }

        const data = (await response.json()) as FeedDigestResponse;
        if (cancelled) return;
        setItems(data.items.filter((i) => i.latest_title));
      } catch (error) {
        if (!cancelled) {
          console.warn('Failed to load feed digest:', error);
        }
      }
    };

    void loadDigest();

    return () => {
      cancelled = true;
    };
  }, [getToken, isLoaded, isSignedIn]);

  // Auto-scroll loop via requestAnimationFrame
  useEffect(() => {
    if (items.length === 0) return;
    const el = scrollRef.current;
    if (!el) return;

    // Measure one set of cards dynamically (scrollWidth / 3 since we triple)
    const halfWidth = el.scrollWidth / 3;
    const speed = 0.5; // px per frame (~30px/s at 60fps)
    let lastTime = 0;

    const tick = (time: number) => {
      if (lastTime === 0) lastTime = time;
      const delta = time - lastTime;
      lastTime = time;

      if (!dragging.current && Date.now() > pauseUntilRef.current) {
        el.scrollLeft += speed * (delta / 16.67); // normalize to 60fps
        // Seamless loop: when past the first set, jump back
        if (el.scrollLeft >= halfWidth) {
          el.scrollLeft -= halfWidth;
        }
      }
      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [items]);

  // Pause auto-scroll on hover
  const pauseAutoScroll = (seconds: number) => {
    pauseUntilRef.current = Date.now() + seconds * 1000;
  };

  // Mouse drag handlers
  const onPointerDown = (e: React.PointerEvent) => {
    const el = scrollRef.current;
    if (!el) return;
    // Don't capture pointer if clicking on a draggable card — let HTML5 DnD take over
    const target = e.target as HTMLElement;
    if (target.closest('[draggable="true"]')) return;
    dragging.current = true;
    hasDragged.current = false;
    dragStartX.current = e.clientX;
    dragScrollLeft.current = el.scrollLeft;
    el.setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragging.current || !scrollRef.current) return;
    const dx = e.clientX - dragStartX.current;
    if (Math.abs(dx) > 3) hasDragged.current = true;
    scrollRef.current.scrollLeft = dragScrollLeft.current - dx;
  };

  const onPointerUp = (e: React.PointerEvent) => {
    if (!dragging.current) return;
    dragging.current = false;
    scrollRef.current?.releasePointerCapture(e.pointerId);
    // Resume auto-scroll after 3s
    pauseAutoScroll(3);
  };

  // Prevent click navigation if user was dragging
  const onCardClick = (e: React.MouseEvent) => {
    if (hasDragged.current) {
      e.preventDefault();
      e.stopPropagation();
    }
  };

  // Wheel horizontal scroll support
  const onWheel = (e: React.WheelEvent) => {
    if (!scrollRef.current) return;
    // Use deltaX if available (trackpad), otherwise convert deltaY
    const delta = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
    scrollRef.current.scrollLeft += delta;
    pauseAutoScroll(3);
  };

  if (items.length === 0) return null;

  // Triple the items for smoother infinite loop
  const tripled = [...items, ...items, ...items];

  return (
    <div
      className="fixed inset-x-0 bottom-0 z-50 h-[112px] overflow-hidden bg-gradient-to-t from-background/90 to-background/60 backdrop-blur-sm"
      onMouseEnter={() => pauseAutoScroll(999999)}
      onMouseLeave={() => pauseAutoScroll(0.5)}
    >
      {/* 左侧标签 */}
      <div className="absolute bottom-0 left-0 top-0 z-10 flex items-center bg-gradient-to-r from-background via-background/90 to-transparent px-4 pr-12 pointer-events-none">
        <div className="flex items-center gap-2 rounded-full border border-orange-500/20 bg-orange-500/10 px-3 py-1.5 shadow-sm backdrop-blur-md">
          <div className="h-2 w-2 rounded-full bg-orange-500/80 animate-pulse"></div>
          <span className="text-xs font-semibold tracking-wide text-orange-600 dark:text-orange-400">
            RSS 最新文章
          </span>
        </div>
      </div>

      {/* 右侧中英切换按钮 */}
      <div className="absolute bottom-0 right-0 top-0 z-10 flex items-center bg-gradient-to-l from-background via-background/90 to-transparent px-4 pl-12">
        <button
          onClick={() => setLang((l) => (l === 'zh' ? 'en' : 'zh'))}
          className="flex items-center gap-1.5 rounded-full border border-border bg-card/90 px-3 py-1.5 text-[11px] font-medium text-muted-foreground shadow-sm backdrop-blur-md transition-colors hover:border-orange-500/30 hover:text-foreground"
        >
          <span className={lang === 'zh' ? 'text-orange-600 dark:text-orange-400' : ''}>中</span>
          <span className="text-border">/</span>
          <span className={lang === 'en' ? 'text-orange-600 dark:text-orange-400' : ''}>EN</span>
        </button>
      </div>

      {/* Scrollable track */}
      <div
        ref={scrollRef}
        className="flex h-full cursor-grab items-center gap-4 overflow-x-scroll py-2 pl-4 pr-4 active:cursor-grabbing scrollbar-none"
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onWheel={onWheel}
        onClickCapture={onCardClick}
      >
        {tripled.map((item, i) => (
          <FeedCard key={`${item.feed_name}-${i}`} item={item} lang={lang} />
        ))}
      </div>
    </div>
  );
}

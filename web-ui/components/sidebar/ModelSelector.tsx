'use client';

import { memo } from 'react';
import { ChevronDown, Check, Cpu } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useChatStore } from '@/hooks/useChat';
import { cn } from '@/lib/utils';
import type { ModelInfo } from '@/lib/api';

interface ModelSelectorProps {
  className?: string;
}

export const ModelSelector = memo(function ModelSelector({
  className,
}: ModelSelectorProps) {
  const { models, currentModelProvider, currentModelName, setModel } = useChatStore();

  // Group models by provider
  const modelsByProvider = models.reduce(
    (acc, model) => {
      if (!acc[model.provider]) {
        acc[model.provider] = [];
      }
      acc[model.provider].push(model);
      return acc;
    },
    {} as Record<string, ModelInfo[]>
  );

  // Get current model display name
  const currentModel = models.find(
    (m) => m.provider === currentModelProvider && m.name === currentModelName
  );

  const providerOrder = ['aliyun', 'anthropic', 'openai', 'openrouter'];
  const sortedProviders = Object.keys(modelsByProvider).sort(
    (a, b) => providerOrder.indexOf(a) - providerOrder.indexOf(b)
  );

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          className={cn('w-full justify-between', className)}
        >
          <div className="flex items-center gap-2 truncate">
            <Cpu className="h-4 w-4 shrink-0" />
            <span className="truncate">
              {currentModel?.display_name || currentModelName}
            </span>
          </div>
          <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        {sortedProviders.map((provider, index) => (
          <div key={provider}>
            {index > 0 && <DropdownMenuSeparator />}
            <DropdownMenuLabel className="capitalize">
              {provider}
            </DropdownMenuLabel>
            {modelsByProvider[provider].map((model) => (
              <DropdownMenuItem
                key={`${model.provider}-${model.name}`}
                onClick={() => setModel(model.provider, model.name)}
              >
                <Check
                  className={cn(
                    'h-4 w-4 mr-2',
                    model.provider === currentModelProvider &&
                      model.name === currentModelName
                      ? 'opacity-100'
                      : 'opacity-0'
                  )}
                />
                <div className="flex flex-col">
                  <span>{model.display_name}</span>
                  {model.supports_thinking && (
                    <span className="text-xs text-muted-foreground">
                      Supports thinking
                    </span>
                  )}
                </div>
              </DropdownMenuItem>
            ))}
          </div>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
});

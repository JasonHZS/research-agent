'use client';

import { memo } from 'react';
import {
  ChevronDown,
  Check,
  Cpu,
  Sparkles,
  Brain,
  Cloud,
  Network
} from 'lucide-react';
import type { ButtonProps } from '@/components/ui/button';
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
import type { ModelInfo } from '@/lib/types';

interface ModelSelectorProps {
  className?: string;
  buttonVariant?: ButtonProps['variant'];
  buttonSize?: ButtonProps['size'];
  fullWidth?: boolean;
  align?: 'start' | 'end';
}

const PROVIDER_ICONS: Record<string, React.ElementType> = {
  openai: Sparkles,
  anthropic: Brain,
  aliyun: Cloud,
  openrouter: Network,
};

export const ModelSelector = memo(function ModelSelector({
  className,
  buttonVariant = 'outline',
  buttonSize = 'default',
  fullWidth = true,
  align = 'start',
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

  // Get current model display name and format it
  const currentModel = models.find(
    (m) => m.provider === currentModelProvider && m.name === currentModelName
  );
  
  // Capitalize provider name (e.g., 'aliyun' -> 'Aliyun')
  const formattedProvider = currentModelProvider 
    ? currentModelProvider.charAt(0).toUpperCase() + currentModelProvider.slice(1) 
    : '';
    
  // Format display text as "Provider/ModelName"
  let displayModelName = currentModel?.display_name || currentModelName;

  // Clean up display name
  if (currentModelProvider === 'aliyun') {
    displayModelName = displayModelName.replace(/^Aliyun\s+/i, '');
  } else if (currentModelProvider === 'openrouter') {
    displayModelName = displayModelName.replace(/\s*\(OpenRouter\)$/i, '');
  }

  const displayText = `${formattedProvider}/${displayModelName}`;

  const providerOrder = ['aliyun', 'anthropic', 'openai', 'openrouter'];
  const sortedProviders = Object.keys(modelsByProvider).sort(
    (a, b) => providerOrder.indexOf(a) - providerOrder.indexOf(b)
  );

  const ProviderIcon = currentModelProvider
    ? PROVIDER_ICONS[currentModelProvider] || Cpu
    : Cpu;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant={buttonVariant}
          size={buttonSize}
          className={cn(
            fullWidth ? 'w-full justify-between' : 'justify-between',
            'focus-visible:ring-0 focus-visible:ring-offset-0',
            className
          )}
        >
          <div className="flex items-center gap-2 truncate">
            <ProviderIcon className="h-4 w-4 shrink-0" />
            <span className="truncate">
              {displayText}
            </span>
          </div>
          <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align={align} className="w-64">
        {sortedProviders.map((provider, index) => (
          <div key={provider}>
            {index > 0 && <DropdownMenuSeparator />}
            <DropdownMenuLabel className="capitalize">
              {provider}
            </DropdownMenuLabel>
            {modelsByProvider[provider].map((model) => {
              // Clean up display name in dropdown
              let itemDisplayName = model.display_name;
              if (model.provider === 'aliyun') {
                itemDisplayName = itemDisplayName.replace(/^Aliyun\s+/i, '');
              } else if (model.provider === 'openrouter') {
                itemDisplayName = itemDisplayName.replace(/\s*\(OpenRouter\)$/i, '');
              }

              return (
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
                    <span>{itemDisplayName}</span>
                    {model.supports_thinking && (
                      <span className="text-xs text-muted-foreground">
                        Supports thinking
                      </span>
                    )}
                  </div>
                </DropdownMenuItem>
              );
            })}
          </div>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
});

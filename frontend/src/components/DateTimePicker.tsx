import { useEffect, useMemo, useState } from "react";

import { Icon } from "@/components/ds/Icon";
import { Calendar } from "@/components/ui/calendar";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

type DateTimePickerProps = {
  label: string;
  value: Date | null;
  onChange: (value: Date | null) => void;
  placeholder?: string;
  className?: string;
};

function formatPickerValue(value: Date | null): string {
  if (!value) return "";
  return value.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function splitDateTime(value: Date | null): { date: Date | undefined; hour: number; minute: number } {
  const base = value ?? new Date();
  return {
    date: value ? new Date(base.getFullYear(), base.getMonth(), base.getDate()) : undefined,
    hour: base.getHours(),
    minute: base.getMinutes(),
  };
}

function buildDateTime(date: Date | undefined, hour: number, minute: number): Date | null {
  if (!date) return null;
  const result = new Date(date);
  result.setHours(hour, minute, 0, 0);
  return result;
}

const HOURS = Array.from({ length: 24 }, (_, i) => i);
const MINUTES = Array.from({ length: 60 }, (_, i) => i);

export function DateTimePicker({
  label,
  value,
  onChange,
  placeholder = "Pick date & time",
  className,
}: DateTimePickerProps) {
  const [open, setOpen] = useState(false);
  const [draftDate, setDraftDate] = useState<Date | undefined>();
  const [draftHour, setDraftHour] = useState(0);
  const [draftMinute, setDraftMinute] = useState(0);

  useEffect(() => {
    if (!open) return;
    const parts = splitDateTime(value);
    setDraftDate(parts.date);
    setDraftHour(parts.hour);
    setDraftMinute(parts.minute);
  }, [open, value]);

  const display = useMemo(() => formatPickerValue(value), [value]);

  const apply = () => {
    const next = buildDateTime(draftDate, draftHour, draftMinute);
    if (!next) return;
    onChange(next);
    setOpen(false);
  };

  const clear = () => {
    onChange(null);
    setOpen(false);
  };

  return (
    <div className={cn("flex items-center", className)}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            className={cn(
              "h-8 justify-start gap-2 px-2.5 text-sm font-normal",
              )}
          >
            <Icon name="calendar" className="text-subtle-foreground" />
            <span className="text-muted-foreground">{label}</span>
            {display ? <span className="truncate text-foreground">{display}</span> : <span className="sr-only">{placeholder}</span>}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar
            mode="single"
            selected={draftDate}
            onSelect={setDraftDate}
            initialFocus
          />
          <div className="border-t border-border px-3 py-3 space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground w-10">Time</span>
              <select
                aria-label={`${label} hour`}
                value={draftHour}
                onChange={(e) => setDraftHour(Number(e.target.value))}
                className="field field-sm flex-1"
              >
                {HOURS.map((hour) => (
                  <option key={hour} value={hour}>
                    {String(hour).padStart(2, "0")}:00
                  </option>
                ))}
              </select>
              <span className="text-muted-foreground">:</span>
              <select
                aria-label={`${label} minute`}
                value={draftMinute}
                onChange={(e) => setDraftMinute(Number(e.target.value))}
                className="field field-sm flex-1"
              >
                {MINUTES.map((minute) => (
                  <option key={minute} value={minute}>
                    {String(minute).padStart(2, "0")}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center justify-end gap-2">
              <Button type="button" variant="ghost" size="sm" onClick={clear}>
                Clear
              </Button>
              <Button type="button" size="sm" disabled={!draftDate} onClick={apply}>
                Apply
              </Button>
            </div>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}

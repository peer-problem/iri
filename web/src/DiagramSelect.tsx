import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent } from "react";

export function DiagramSelect({ label, options, value, onChange }: {
  label: string;
  options: string[];
  value: number;
  onChange: (value: number) => void;
}) {
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(value);

  useEffect(() => {
    if (!open) return;
    list.current?.focus({ preventScroll: true });
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);

  const show = () => { setActive(value); setOpen(true); };
  const choose = (index: number) => {
    onChange(index);
    setOpen(false);
    trigger.current?.focus({ preventScroll: true });
  };
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === "Tab") {
      trigger.current?.focus({ preventScroll: true });
      setOpen(false);
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      trigger.current?.focus({ preventScroll: true });
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      choose(active);
    } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      setActive(index => event.key === "Home" ? 0 : event.key === "End" ? options.length - 1
        : (index + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length);
    }
  };

  return <div className="diagram-select" ref={root} onBlur={event => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false);
  }}>
    <button ref={trigger} type="button" className="diagram-select-trigger"
      aria-label={`${label}: ${options[value]}`} aria-haspopup="listbox"
      aria-expanded={open} aria-controls={open ? id : undefined}
      onClick={() => open ? setOpen(false) : show()}
      onKeyDown={event => {
        if (["ArrowDown", "ArrowUp"].includes(event.key)) { event.preventDefault(); show(); }
      }}>
      <span>{options[value]}</span>
      <svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" /></svg>
    </button>
    {open && <div ref={list} id={id} className="diagram-select-menu" role="listbox"
      tabIndex={-1} aria-label={label} aria-activedescendant={`${id}-${active}`} onKeyDown={onKeyDown}>
      {options.map((option, index) => <div key={option} id={`${id}-${index}`} role="option"
        aria-selected={value === index} data-active={active === index}
        className="diagram-select-option" onPointerMove={() => setActive(index)} onClick={() => choose(index)}>
        <span>{option}</span><span className="diagram-select-check" aria-hidden="true">{value === index ? "✓" : ""}</span>
      </div>)}
    </div>}
  </div>;
}

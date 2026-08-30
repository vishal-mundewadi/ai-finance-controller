import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const BOOT_LINES = [
  "Initializing reconciliation engine...",
  "Loading settlement data...",
  "Cross-checking payments, refunds, settlements...",
  "Ready to be a Investigator",
];

const TYPE_SPEED = 45;       // ms per character — lower = faster typing
const LINE_PAUSE = 500;      // pause after a line finishes, before the next starts
const HOLD_BEFORE_TITLE = 600;
const TITLE_HOLD = 1800;     // how long the big title stays before fading out

interface BootIntroProps {
  onComplete: () => void;
}

function BootIntro({ onComplete }: BootIntroProps) {
  const [lineIndex, setLineIndex] = useState(0);
  const [charIndex, setCharIndex] = useState(0);
  const [completedLines, setCompletedLines] = useState<string[]>([]);
  const [showTitle, setShowTitle] = useState(false);
  const [exiting, setExiting] = useState(false);

  // Types out the current line, one character at a time
  useEffect(() => {
    if (lineIndex >= BOOT_LINES.length) return;
    const currentLine = BOOT_LINES[lineIndex];

    if (charIndex < currentLine.length) {
      const timer = setTimeout(() => setCharIndex(charIndex + 1), TYPE_SPEED);
      return () => clearTimeout(timer);
    } else {
      const timer = setTimeout(() => {
        setCompletedLines((prev) => [...prev, currentLine]);
        setLineIndex(lineIndex + 1);
        setCharIndex(0);
      }, LINE_PAUSE);
      return () => clearTimeout(timer);
    }
  }, [lineIndex, charIndex]);

  // Once every line has typed out, reveal the title, hold, then exit
  useEffect(() => {
    if (lineIndex >= BOOT_LINES.length) {
      const titleTimer = setTimeout(() => setShowTitle(true), HOLD_BEFORE_TITLE);
      const exitTimer = setTimeout(() => setExiting(true), HOLD_BEFORE_TITLE + TITLE_HOLD);
      const completeTimer = setTimeout(() => onComplete(), HOLD_BEFORE_TITLE + TITLE_HOLD + 700);
      return () => {
        clearTimeout(titleTimer);
        clearTimeout(exitTimer);
        clearTimeout(completeTimer);
      };
    }
  }, [lineIndex, onComplete]);

  const currentTypedText =
    lineIndex < BOOT_LINES.length ? BOOT_LINES[lineIndex].slice(0, charIndex) : "";

  return (
    <AnimatePresence>
      {!exiting && (
        <motion.div
          exit={{ opacity: 0 }}
          transition={{ duration: 0.8 }}
          className="fixed inset-0 bg-white flex flex-col items-center justify-center gap-2 px-4"
        >
          {!showTitle && (
            <div className="font-mono text-left">
              {completedLines.map((line, i) => (
                <p key={i} className="text-black font-bold tracking-wide text-base md:text-lg mb-2">
                  {line}
                </p>
              ))}
              {lineIndex < BOOT_LINES.length && (
                <p className="text-black font-bold tracking-wide text-base md:text-lg mb-2">
                  {currentTypedText}
                  <span className="inline-block w-[2px] h-[1em] bg-black ml-1 animate-pulse" />
                </p>
              )}
            </div>
          )}

          {showTitle && (
            <motion.h1
              initial={{ opacity: 0, scale: 0.9, letterSpacing: "0.3em" }}
              animate={{ opacity: 1, scale: 1, letterSpacing: "0em" }}
              transition={{ duration: 1.1, ease: "easeOut" }}
              className="text-5xl md:text-7xl font-extrabold text-amber-600 tracking-tight text-center"
            >
              AI Finance and Settlement Investigator
            </motion.h1>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default BootIntro;
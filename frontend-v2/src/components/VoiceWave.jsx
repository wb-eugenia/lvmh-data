import React, { useEffect, useRef, useState } from 'react'

/**
 * VoiceWave - Elegant audio visualizer for LVMH Voice-to-Tag
 * A minimal, gold-accented wave that responds to audio input
 */
export default function VoiceWave({ isRecording, audioStream }) {
    const canvasRef = useRef(null)
    const animationRef = useRef(null)
    const analyserRef = useRef(null)
    const [bars, setBars] = useState(Array(24).fill(0.1))

    useEffect(() => {
        if (!isRecording || !audioStream) {
            // Reset to minimal state
            setBars(Array(24).fill(0.1))
            return
        }

        // Setup audio analyzer
        const audioContext = new (window.AudioContext || window.webkitAudioContext)()
        const analyser = audioContext.createAnalyser()
        analyser.fftSize = 64
        analyser.smoothingTimeConstant = 0.8

        const source = audioContext.createMediaStreamSource(audioStream)
        source.connect(analyser)
        analyserRef.current = analyser

        const dataArray = new Uint8Array(analyser.frequencyBinCount)

        const animate = () => {
            analyser.getByteFrequencyData(dataArray)

            // Take middle frequencies for smoother visualization
            const newBars = []
            for (let i = 0; i < 24; i++) {
                const index = Math.floor(i * (dataArray.length / 24))
                // Normalize to 0-1 range with some minimum
                const value = Math.max(0.1, dataArray[index] / 255)
                newBars.push(value)
            }

            setBars(newBars)
            animationRef.current = requestAnimationFrame(animate)
        }

        animate()

        return () => {
            cancelAnimationFrame(animationRef.current)
            audioContext.close()
        }
    }, [isRecording, audioStream])

    return (
        <div className="flex items-center justify-center gap-[3px] h-16 w-full max-w-xs mx-auto">
            {bars.map((height, i) => (
                <div
                    key={i}
                    className="w-[2px] rounded-full transition-all duration-75"
                    style={{
                        height: `${Math.max(4, height * 48)}px`,
                        background: isRecording
                            ? `linear-gradient(to top, rgba(212, 175, 55, 0.4), rgba(212, 175, 55, ${0.6 + height * 0.4}))`
                            : 'rgba(138, 138, 138, 0.3)',
                        animationDelay: `${i * 50}ms`,
                    }}
                />
            ))}
        </div>
    )
}

/**
 * Simple pulse wave for when no audio stream is available
 * Uses CSS animations for a minimal aesthetic
 */
export function VoiceWaveSimple({ isRecording }) {
    const barCount = 12

    return (
        <div className="flex items-center justify-center gap-1 h-8 w-full max-w-[120px] mx-auto">
            {Array.from({ length: barCount }).map((_, i) => {
                const delay = i * 0.08
                const baseHeight = isRecording ? 4 : 2

                return (
                    <div
                        key={i}
                        className={`w-[1.5px] rounded-full ${isRecording
                                ? 'bg-champagne animate-pulse'
                                : 'bg-mist/30'
                            }`}
                        style={{
                            height: `${baseHeight + (isRecording ? Math.sin(i * 0.5) * 12 + 12 : 0)}px`,
                            animationDelay: `${delay}s`,
                            transition: 'height 150ms ease-out',
                        }}
                    />
                )
            })}
        </div>
    )
}

/**
 * Horizontal line wave - ultra minimal
 */
export function VoiceWaveLine({ isRecording }) {
    return (
        <div className="relative w-full max-w-md mx-auto h-[1px] overflow-hidden">
            {/* Base line */}
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-mist/20 to-transparent" />

            {/* Active wave */}
            {isRecording && (
                <div
                    className="absolute inset-0 bg-gradient-to-r from-transparent via-champagne to-transparent animate-pulse"
                    style={{
                        animation: 'pulse 1.5s ease-in-out infinite',
                    }}
                />
            )}

            {/* Center glow when recording */}
            {isRecording && (
                <div
                    className="absolute left-1/2 -translate-x-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-champagne blur-sm"
                    style={{
                        boxShadow: '0 0 10px rgba(212, 175, 55, 0.5)',
                    }}
                />
            )}
        </div>
    )
}

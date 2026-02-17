/**
 * Edge Transcription Module - Whisper WASM
 * Transforms speech to text directly in the browser
 * Uses Transformers.js (WebGPU/WebAssembly)
 */

let transcriberPipeline = null;
let isLoading = false;
let loadProgressCallback = null;

export function setLoadProgressCallback(callback) {
  loadProgressCallback = callback;
}

export async function loadWhisperModel(modelSize = 'base') {
  if (transcriberPipeline) {
    return transcriberPipeline;
  }

  if (isLoading) {
    return new Promise((resolve) => {
      const checkReady = setInterval(() => {
        if (transcriberPipeline) {
          clearInterval(checkReady);
          resolve(transcriberPipeline);
        }
      }, 100);
    });
  }

  isLoading = true;

  try {
    const { pipeline, env } = await import('@xenova/transformers');
    
    env.allowLocalModels = false;
    env.useBrowserCache = true;

    const modelName = `Xenova/whisper-${modelSize}`;
    
    if (loadProgressCallback) {
      loadProgressCallback({ status: 'downloading', progress: 0 });
    }

    transcriberPipeline = await pipeline(
      'automatic-speech-recognition',
      modelName,
      {
        progress_callback: (progress) => {
          if (loadProgressCallback && progress.status === 'downloading') {
            loadProgressCallback({
              status: 'downloading',
              progress: Math.round(progress.progress || 0)
            });
          }
        }
      }
    );

    if (loadProgressCallback) {
      loadProgressCallback({ status: 'ready', progress: 100 });
    }

    return transcriberPipeline;
  } catch (error) {
    console.error('Failed to load Whisper model:', error);
    isLoading = false;
    throw error;
  }
}

export async function transcribeAudio(audioBlob, language = 'fr') {
  if (!transcriberPipeline) {
    await loadWhisperModel('base');
  }

  try {
    let audioData;
    
    // Handle different audio formats
    if (audioBlob instanceof Blob) {
      const arrayBuffer = await audioBlob.arrayBuffer();
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      
      // Decode the audio - works with webm, wav, mp3, etc.
      const decodedAudio = await audioContext.decodeAudioData(arrayBuffer);
      
      // Convert to mono Float32Array (Whisper expects this)
      const channelData = decodedAudio.getChannelData(0);
      
      // Resample to 16kHz if needed (Whisper expects 16kHz)
      const sampleRate = decodedAudio.sampleRate;
      if (sampleRate !== 16000) {
        audioData = resampleAudio(channelData, sampleRate, 16000);
      } else {
        audioData = channelData;
      }
    } else if (audioBlob instanceof Float32Array) {
      audioData = audioBlob;
    } else {
      throw new Error('Unsupported audio format');
    }
    
    const result = await transcriberPipeline(audioData, {
      language: language,
      task: 'transcribe',
      chunk_length_s: 30,
      return_timestamps: false
    });

    return {
      text: result.text || '',
      provider: 'whisper-wasm',
      language: language
    };
  } catch (error) {
    console.error('Transcription error:', error);
    throw error;
  }
}

// Simple linear resampling
function resampleAudio(float32Array, fromSampleRate, toSampleRate) {
  if (fromSampleRate === toSampleRate) return float32Array;
  
  const ratio = fromSampleRate / toSampleRate;
  const newLength = Math.round(float32Array.length / ratio);
  const result = new Float32Array(newLength);
  
  for (let i = 0; i < newLength; i++) {
    const srcIndex = i * ratio;
    const srcIndexFloor = Math.floor(srcIndex);
    const frac = srcIndex - srcIndexFloor;
    
    if (srcIndexFloor + 1 < float32Array.length) {
      result[i] = float32Array[srcIndexFloor] * (1 - frac) + 
                  float32Array[srcIndexFloor + 1] * frac;
    } else {
      result[i] = float32Array[srcIndexFloor];
    }
  }
  
  return result;
}

export async function transcribeAudioFile(audioFile, language = 'fr') {
  const blob = new Blob([await audioFile.arrayBuffer()], { type: audioFile.type });
  return transcribeAudio(blob, language);
}

export function isModelLoaded() {
  return transcriberPipeline !== null;
}

export function unloadModel() {
  transcriberPipeline = null;
  isLoading = false;
}

export default {
  loadWhisperModel,
  transcribeAudio,
  transcribeAudioFile,
  isModelLoaded,
  unloadModel,
  setLoadProgressCallback
};

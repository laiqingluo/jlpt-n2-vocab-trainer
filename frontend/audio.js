const reviewAudio = new Audio();
const wordAudioCache = {};
const cnAudioCache = {};


async function fetchAudio(path, text) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ word: text }),
  });
  if (!response.ok) throw new Error("audio request failed");
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}


function playAudioSrc(src) {
  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      reviewAudio.onended = null;
      reviewAudio.onerror = null;
      resolve();
    };
    reviewAudio.onended = finish;
    reviewAudio.onerror = finish;
    reviewAudio.src = src;
    reviewAudio.muted = false;
    reviewAudio.playsInline = true;
    reviewAudio.play().catch(finish);
  });
}


async function playWordAudio(word) {
  if (!word) return;
  const text = word.reading || word.word || word;
  if (!text) return;
  try {
    if (!wordAudioCache[text]) {
      wordAudioCache[text] = fetchAudio("/api/word_audio", text);
    }
    await playAudioSrc(await wordAudioCache[text]);
  } catch {
    toast("播放日语音频失败");
  }
}


async function playChineseAudio(text) {
  const key = text || "暂无释义";
  try {
    if (!cnAudioCache[key]) {
      cnAudioCache[key] = fetchAudio("/api/cn_audio", key);
    }
    await playAudioSrc(await cnAudioCache[key]);
  } catch {
    if (!("speechSynthesis" in window)) {
      toast("播放中文音频失败");
      return;
    }
    const utter = new SpeechSynthesisUtterance(key);
    utter.lang = "zh-CN";
    utter.rate = 0.92;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utter);
  }
}

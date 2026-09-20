using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading.Tasks;
using UnityEngine;

namespace Axiom.Body
{
    public sealed class WindowsSpeechOutput
    {
        private readonly object _gate = new object();
        private Process _currentProcess;

        public Task<string> SynthesizeWavAsync(VoiceExpressionIntent intent)
        {
#if UNITY_STANDALONE_WIN || UNITY_EDITOR_WIN
            return Task.Run(() => SynthesizeWavBlocking(intent));
#else
            throw new PlatformNotSupportedException(
                "The current desktop Mouth V0.2 uses Windows System.Speech."
            );
#endif
        }

        public void Stop()
        {
#if UNITY_STANDALONE_WIN || UNITY_EDITOR_WIN
            lock (_gate)
            {
                if (_currentProcess == null)
                {
                    return;
                }

                try
                {
                    if (!_currentProcess.HasExited)
                    {
                        _currentProcess.Kill();
                    }
                }
                catch
                {
                    // The process may already be exiting.
                }
            }
#endif
        }

#if UNITY_STANDALONE_WIN || UNITY_EDITOR_WIN
        private string SynthesizeWavBlocking(VoiceExpressionIntent intent)
        {
            if (intent == null || string.IsNullOrWhiteSpace(intent.text))
            {
                throw new ArgumentException("Voice intent requires text.", nameof(intent));
            }

            VoiceIntentMetadata metadata = intent.metadata ?? new VoiceIntentMetadata();
            float rate = Mathf.Clamp(metadata.rate, 0.1f, 10f);
            float pitch = Mathf.Clamp(metadata.pitch, 0f, 2f);
            float volume = Mathf.Clamp01(metadata.volume);

            int ratePercent = Mathf.Clamp(
                Mathf.RoundToInt((rate - 1f) * 100f),
                -90,
                300
            );
            int pitchPercent = Mathf.Clamp(
                Mathf.RoundToInt((pitch - 1f) * 100f),
                -100,
                100
            );
            int volumePercent = Mathf.RoundToInt(volume * 100f);

            string outputPath = Path.Combine(
                Path.GetTempPath(),
                "axiom-voice-" + Guid.NewGuid().ToString("N") + ".wav"
            );

            string textBase64 = Convert.ToBase64String(
                Encoding.UTF8.GetBytes(intent.text.Trim())
            );
            string voiceBase64 = Convert.ToBase64String(
                Encoding.UTF8.GetBytes(metadata.voice_name ?? string.Empty)
            );
            string pathBase64 = Convert.ToBase64String(
                Encoding.UTF8.GetBytes(outputPath)
            );

            string script = string.Join(
                ";",
                "Add-Type -AssemblyName System.Speech",
                "$text=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" +
                    textBase64 + "'))",
                "$voice=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" +
                    voiceBase64 + "'))",
                "$path=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" +
                    pathBase64 + "'))",
                "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer",
                "if($voice){try{$s.SelectVoice($voice)}catch{}}",
                "$s.Volume=" + volumePercent,
                "$culture=$s.Voice.Culture.Name",
                "$escaped=[System.Security.SecurityElement]::Escape($text)",
                "$ssml=\"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='$culture'><prosody rate='" +
                    (ratePercent >= 0 ? "+" : string.Empty) + ratePercent +
                    "%' pitch='" + (pitchPercent >= 0 ? "+" : string.Empty) +
                    pitchPercent + "%'>$escaped</prosody></speak>\"",
                "$s.SetOutputToWaveFile($path)",
                "$s.SpeakSsml($ssml)",
                "$s.Dispose()"
            );

            string encodedCommand = Convert.ToBase64String(
                Encoding.Unicode.GetBytes(script)
            );

            ProcessStartInfo startInfo = new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments =
                    "-NoLogo -NoProfile -NonInteractive -EncodedCommand " +
                    encodedCommand,
                UseShellExecute = false,
                CreateNoWindow = true,
                WindowStyle = ProcessWindowStyle.Hidden
            };

            using Process process = new Process { StartInfo = startInfo };
            lock (_gate)
            {
                _currentProcess = process;
            }

            try
            {
                if (!process.Start())
                {
                    throw new InvalidOperationException(
                        "Windows speech synthesis process could not start."
                    );
                }

                process.WaitForExit();
                if (process.ExitCode != 0)
                {
                    throw new InvalidOperationException(
                        "Windows speech synthesis exited with code " +
                        process.ExitCode + "."
                    );
                }

                if (!File.Exists(outputPath) || new FileInfo(outputPath).Length == 0)
                {
                    throw new InvalidOperationException(
                        "Windows speech synthesis did not produce audio."
                    );
                }

                return outputPath;
            }
            catch
            {
                TryDelete(outputPath);
                throw;
            }
            finally
            {
                lock (_gate)
                {
                    if (ReferenceEquals(_currentProcess, process))
                    {
                        _currentProcess = null;
                    }
                }
            }
        }
#endif

        public static void TryDelete(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                return;
            }

            try
            {
                if (File.Exists(path))
                {
                    File.Delete(path);
                }
            }
            catch
            {
                // Temporary audio cleanup must not crash the Body.
            }
        }
    }
}

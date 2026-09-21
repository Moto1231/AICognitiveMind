using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using UnityEngine;

namespace Axiom.Body
{
    public sealed class AxiomAdminRuntime : MonoBehaviour
    {
        private static readonly string[] MemoryClasses =
        {
            "working",
            "episodic",
            "semantic",
            "procedural",
            "identity",
            "reflective"
        };

        private MindApiClient _client;
        private AxiomMindDataRuntime _mindData;
        private string _pin = string.Empty;
        private string _status = "Administrator authorization required.";
        private bool _authorized;
        private bool _busy;
        private Vector2 _scroll = Vector2.zero;

        private DesktopMemoryItem _selected;
        private string _editContent = string.Empty;
        private string _editAssociations = string.Empty;
        private string _editGrounding = string.Empty;
        private int _editClassIndex;

        public bool Authorized => _authorized;
        public bool Busy => _busy;
        public bool EditingMemory => _selected != null;
        public string Status => _status;

        public void Attach(
            MindApiClient client,
            AxiomMindDataRuntime mindData
        )
        {
            _client = client;
            _mindData = mindData;
            _authorized = false;
            _selected = null;
            _status = "Administrator authorization required.";
        }

        public void DrawGUI(Action close)
        {
            const float width = 680f;
            float height = Mathf.Min(
                760f,
                Mathf.Max(500f, Screen.height - 36f)
            );

            GUI.Box(new Rect(18f, 18f, width, height), "Admin");

            if (GUI.Button(new Rect(34f, 48f, 112f, 30f), "Back to Body"))
            {
                _selected = null;
                close?.Invoke();
                return;
            }

            GUI.Label(
                new Rect(158f, 52f, width - 176f, 24f),
                _status
            );

            if (!_authorized)
            {
                DrawAuthorization(width);
                return;
            }

            if (_selected != null)
            {
                DrawMemoryEditor(width, height);
                return;
            }

            DrawMemoryList(width, height);
        }

        private void DrawAuthorization(float width)
        {
            GUI.Label(
                new Rect(34f, 104f, width - 68f, 42f),
                "Enter the administrator PIN for this session. " +
                "Leave blank when the server does not require one."
            );

            GUI.Label(new Rect(34f, 160f, 80f, 24f), "Admin PIN");
            _pin = GUI.PasswordField(
                new Rect(116f, 156f, 220f, 30f),
                _pin,
                '*',
                120
            );

            GUI.enabled = !_busy && _client != null;
            if (GUI.Button(new Rect(348f, 156f, 110f, 30f), "Authorize"))
            {
                _ = AuthorizeAsync(_pin);
            }
            GUI.enabled = true;

            GUI.Label(
                new Rect(34f, 206f, width - 68f, 42f),
                "The PIN is kept in memory only and is not saved to disk."
            );
        }

        private void DrawMemoryList(float width, float height)
        {
            if (_mindData == null)
            {
                GUI.Label(
                    new Rect(34f, 104f, width - 68f, 40f),
                    "Memory data is unavailable."
                );
                return;
            }

            GUI.Label(new Rect(34f, 96f, 58f, 24f), "Search");
            _mindData.MemorySearch = GUI.TextField(
                new Rect(92f, 92f, width - 296f, 28f),
                _mindData.MemorySearch ?? string.Empty,
                200
            );

            GUI.enabled = !_busy && !_mindData.LoadingMemory;
            if (GUI.Button(new Rect(width - 190f, 92f, 72f, 28f), "Search"))
            {
                _scroll = Vector2.zero;
                _ = _mindData.LoadMemoryAsync(0);
            }
            if (GUI.Button(new Rect(width - 108f, 92f, 72f, 28f), "Refresh"))
            {
                _ = _mindData.LoadMemoryAsync(
                    _mindData.MemoryPage.offset
                );
            }
            GUI.enabled = true;

            DesktopMemoryPage page =
                _mindData.MemoryPage ?? new DesktopMemoryPage();
            DesktopMemoryItem[] items =
                page.items ?? Array.Empty<DesktopMemoryItem>();

            Rect viewport = new Rect(
                34f,
                136f,
                width - 50f,
                height - 230f
            );
            float contentHeight = Mathf.Max(
                viewport.height - 4f,
                items.Length * 94f
            );

            _scroll = GUI.BeginScrollView(
                viewport,
                _scroll,
                new Rect(0f, 0f, width - 86f, contentHeight)
            );

            for (int index = 0; index < items.Length; index++)
            {
                DesktopMemoryItem item = items[index];
                float y = index * 94f;
                GUI.Box(
                    new Rect(0f, y, width - 102f, 84f),
                    string.Empty
                );

                GUI.Label(
                    new Rect(10f, y + 7f, 140f, 22f),
                    (item.memory_class ?? "memory").ToUpperInvariant()
                );
                GUI.Label(
                    new Rect(154f, y + 7f, 170f, 22f),
                    CompactTimestamp(item.formed_at)
                );
                GUI.Label(
                    new Rect(10f, y + 31f, width - 230f, 44f),
                    CompactText(item.content, 210)
                );

                if (
                    GUI.Button(
                        new Rect(width - 194f, y + 28f, 76f, 30f),
                        "Edit"
                    )
                )
                {
                    BeginEdit(item);
                }
            }

            GUI.EndScrollView();

            float footerY = height - 74f;
            GUI.Label(
                new Rect(34f, footerY, width - 270f, 24f),
                _mindData.MemoryStatus
            );

            GUI.enabled =
                !_busy &&
                !_mindData.LoadingMemory &&
                page.offset > 0;
            if (
                GUI.Button(
                    new Rect(width - 222f, footerY - 2f, 86f, 28f),
                    "Previous"
                )
            )
            {
                _scroll = Vector2.zero;
                _ = _mindData.PreviousMemoryAsync();
            }

            GUI.enabled =
                !_busy &&
                !_mindData.LoadingMemory &&
                page.has_more;
            if (
                GUI.Button(
                    new Rect(width - 126f, footerY - 2f, 86f, 28f),
                    "Next"
                )
            )
            {
                _scroll = Vector2.zero;
                _ = _mindData.NextMemoryAsync();
            }
            GUI.enabled = true;
        }

        public void DrawMemoryEditor(float width, float height)
        {
            DesktopMemoryItem original = _selected;
            if (original == null)
            {
                return;
            }

            if (
                GUI.Button(
                    new Rect(34f, 94f, 112f, 28f),
                    "Back to List"
                )
            )
            {
                _selected = null;
                _status = "Administrator authorized.";
                return;
            }

            GUI.Label(
                new Rect(158f, 98f, width - 176f, 24f),
                "Editing " +
                (original.memory_class ?? "memory") +
                " · " +
                CompactTimestamp(original.formed_at)
            );

            GUI.Label(new Rect(34f, 138f, 120f, 24f), "Memory Class");
            _editClassIndex = GUI.SelectionGrid(
                new Rect(34f, 164f, width - 68f, 58f),
                _editClassIndex,
                MemoryClasses,
                3
            );

            GUI.Label(new Rect(34f, 236f, 120f, 24f), "Content");
            _editContent = GUI.TextArea(
                new Rect(34f, 262f, width - 68f, 118f),
                _editContent ?? string.Empty,
                12000
            );

            GUI.Label(
                new Rect(34f, 394f, 180f, 24f),
                "Associations (one per line)"
            );
            _editAssociations = GUI.TextArea(
                new Rect(34f, 420f, width - 68f, 76f),
                _editAssociations ?? string.Empty,
                4000
            );

            GUI.Label(
                new Rect(34f, 510f, 180f, 24f),
                "Grounding (one per line)"
            );
            _editGrounding = GUI.TextArea(
                new Rect(34f, 536f, width - 68f, 76f),
                _editGrounding ?? string.Empty,
                4000
            );

            GUI.enabled =
                !_busy &&
                !string.IsNullOrWhiteSpace(_editContent);
            if (
                GUI.Button(
                    new Rect(34f, height - 72f, 120f, 32f),
                    "Save Revision"
                )
            )
            {
                _ = SaveRevisionAsync();
            }
            GUI.enabled = true;

            GUI.Label(
                new Rect(168f, height - 68f, width - 202f, 28f),
                "Saving revises durable memory and journals the change."
            );
        }

        public async Task AuthorizeAsync(string pin)
        {
            if (_client == null || _busy)
            {
                return;
            }

            _pin = pin ?? string.Empty;
            _busy = true;
            _status = "Authorizing administrator...";
            try
            {
                AdminStatusResponse response =
                    await _client.AdminStatusAsync(_pin);
                _authorized = response.authorized &&
                    response.memory_editing;
                _status = _authorized
                    ? "Administrator authorized."
                    : "Administrator authorization was not accepted.";

                if (_authorized && _mindData != null)
                {
                    await _mindData.LoadMemoryAsync(0);
                }
            }
            catch (Exception exception)
            {
                _authorized = false;
                _status = "Admin authorization failed: " +
                    exception.Message;
                Debug.LogException(exception);
            }
            finally
            {
                _busy = false;
            }
        }

        public void Deauthorize()
        {
            _pin = string.Empty;
            _authorized = false;
            _selected = null;
            _status = "Administrator authorization required.";
        }

        public void BeginEdit(DesktopMemoryItem memory)
        {
            _selected = memory;
            _editContent = memory.content ?? string.Empty;
            _editAssociations = string.Join(
                "\n",
                memory.associations ?? Array.Empty<string>()
            );
            _editGrounding = string.Join(
                "\n",
                memory.grounding ?? Array.Empty<string>()
            );

            int index = Array.IndexOf(
                MemoryClasses,
                memory.memory_class ?? string.Empty
            );
            _editClassIndex = index >= 0 ? index : 0;
            _status = "Editing durable memory.";
        }

        private async Task SaveRevisionAsync()
        {
            if (
                _client == null ||
                _mindData == null ||
                _selected == null ||
                _busy ||
                string.IsNullOrWhiteSpace(_editContent)
            )
            {
                return;
            }

            _busy = true;
            _status = "Saving governed memory revision...";
            try
            {
                DesktopMemoryItem revised =
                    await _client.ReviseMemoryAsync(
                        _pin,
                        _selected,
                        MemoryClasses[
                            Mathf.Clamp(
                                _editClassIndex,
                                0,
                                MemoryClasses.Length - 1
                            )
                        ],
                        _editContent.Trim(),
                        SplitLines(_editAssociations),
                        SplitLines(_editGrounding)
                    );

                _selected = revised;
                _status = "Durable memory revised and journaled.";

                int currentOffset = _mindData.MemoryPage.offset;
                await _mindData.LoadMemoryAsync(currentOffset);
                await _mindData.LoadJournalAsync(0);

                _selected = null;
            }
            catch (Exception exception)
            {
                _status = "Memory revision failed: " + exception.Message;
                Debug.LogException(exception);
            }
            finally
            {
                _busy = false;
            }
        }

        private static string[] SplitLines(string value)
        {
            return (value ?? string.Empty)
                .Split(
                    new[] { '\r', '\n', ',' },
                    StringSplitOptions.RemoveEmptyEntries
                )
                .Select(item => item.Trim())
                .Where(item => !string.IsNullOrEmpty(item))
                .ToArray();
        }

        private static string CompactTimestamp(string timestamp)
        {
            if (
                DateTimeOffset.TryParse(
                    timestamp,
                    out DateTimeOffset parsed
                )
            )
            {
                return parsed.ToLocalTime().ToString(
                    "yyyy-MM-dd HH:mm"
                );
            }

            return CompactText(timestamp, 22);
        }

        private static string CompactText(string value, int maxLength)
        {
            string text = (value ?? string.Empty)
                .Replace("\r", " ")
                .Replace("\n", " ")
                .Trim();

            if (text.Length <= maxLength)
            {
                return text;
            }

            return text.Substring(
                0,
                Mathf.Max(0, maxLength - 1)
            ) + "…";
        }
    }
}

using System;
using System.Threading.Tasks;
using UnityEngine;

namespace Axiom.Body
{
    public sealed class AxiomMindDataRuntime : MonoBehaviour
    {
        private const int PageSize = 12;

        private MindApiClient _client;

        public DesktopMemoryPage MemoryPage { get; private set; } =
            new DesktopMemoryPage();
        public DesktopJournalPage JournalPage { get; private set; } =
            new DesktopJournalPage();

        public string MemorySearch { get; set; } = string.Empty;
        public string JournalSearch { get; set; } = string.Empty;

        public bool LoadingMemory { get; private set; }
        public bool LoadingJournal { get; private set; }

        public string MemoryStatus { get; private set; } = "Memory not loaded.";
        public string JournalStatus { get; private set; } = "Journal not loaded.";

        public void Attach(MindApiClient client)
        {
            _client = client;
        }

        public async Task LoadMemoryAsync(int offset = 0)
        {
            if (_client == null || LoadingMemory)
            {
                return;
            }

            LoadingMemory = true;
            MemoryStatus = "Loading memory...";
            try
            {
                MemoryPage = await _client.MemoryPageAsync(
                    MemorySearch,
                    Mathf.Max(0, offset),
                    PageSize
                );
                MemoryStatus =
                    MemoryPage.total == 0
                        ? "No memories found."
                        : $"Showing {MemoryPage.offset + 1}-" +
                          $"{MemoryPage.offset + MemoryPage.items.Length} " +
                          $"of {MemoryPage.total}.";
            }
            catch (Exception exception)
            {
                MemoryStatus = "Memory failed: " + exception.Message;
                Debug.LogException(exception);
            }
            finally
            {
                LoadingMemory = false;
            }
        }

        public async Task LoadJournalAsync(int offset = 0)
        {
            if (_client == null || LoadingJournal)
            {
                return;
            }

            LoadingJournal = true;
            JournalStatus = "Loading journal...";
            try
            {
                JournalPage = await _client.JournalPageAsync(
                    JournalSearch,
                    Mathf.Max(0, offset),
                    PageSize
                );
                JournalStatus =
                    JournalPage.total == 0
                        ? "No journal entries found."
                        : $"Showing {JournalPage.offset + 1}-" +
                          $"{JournalPage.offset + JournalPage.items.Length} " +
                          $"of {JournalPage.total}.";
            }
            catch (Exception exception)
            {
                JournalStatus = "Journal failed: " + exception.Message;
                Debug.LogException(exception);
            }
            finally
            {
                LoadingJournal = false;
            }
        }

        public Task NextMemoryAsync()
        {
            if (!MemoryPage.has_more)
            {
                return Task.CompletedTask;
            }

            return LoadMemoryAsync(MemoryPage.next_offset);
        }

        public Task PreviousMemoryAsync()
        {
            return LoadMemoryAsync(
                Mathf.Max(0, MemoryPage.offset - PageSize)
            );
        }

        public Task NextJournalAsync()
        {
            if (!JournalPage.has_more)
            {
                return Task.CompletedTask;
            }

            return LoadJournalAsync(JournalPage.next_offset);
        }

        public Task PreviousJournalAsync()
        {
            return LoadJournalAsync(
                Mathf.Max(0, JournalPage.offset - PageSize)
            );
        }

        public async Task RefreshAllAsync()
        {
            await LoadMemoryAsync(0);
            await LoadJournalAsync(0);
        }
    }
}

// Copyright (c) 2026 William Enright. All rights reserved.
// Use, reproduction, modification, distribution, or commercial exploitation
// of this file is prohibited without prior written permission from the
// copyright holder.

using System;
using System.Runtime.InteropServices;
using UnityEngine;

namespace Axiom.Body
{
    /// <summary>
    /// Makes the Windows standalone client area transparent so the desktop is
    /// visible behind Axiom. This intentionally does not run inside the Unity
    /// Editor because changing the editor window itself would be destructive.
    /// </summary>
    public sealed class WindowsDesktopTransparency : MonoBehaviour
    {
#if UNITY_STANDALONE_WIN && !UNITY_EDITOR
        [StructLayout(LayoutKind.Sequential)]
        private struct Margins
        {
            public int cxLeftWidth;
            public int cxRightWidth;
            public int cyTopHeight;
            public int cyBottomHeight;
        }

        [DllImport("user32.dll")]
        private static extern IntPtr GetActiveWindow();

        [DllImport("dwmapi.dll")]
        private static extern int DwmExtendFrameIntoClientArea(
            IntPtr hWnd,
            ref Margins margins
        );

        private IntPtr _window;
#endif

        public bool Active { get; private set; }

        public void Apply(Camera camera)
        {
            if (camera != null)
            {
                camera.clearFlags = CameraClearFlags.SolidColor;
                camera.backgroundColor = new Color(0f, 0f, 0f, 0f);
            }

#if UNITY_STANDALONE_WIN && !UNITY_EDITOR
            _window = GetActiveWindow();
            if (_window == IntPtr.Zero)
            {
                Active = false;
                return;
            }

            Margins margins = new Margins
            {
                cxLeftWidth = -1,
                cxRightWidth = -1,
                cyTopHeight = -1,
                cyBottomHeight = -1
            };

            Active =
                DwmExtendFrameIntoClientArea(
                    _window,
                    ref margins
                ) == 0;
#else
            Active = false;
#endif
        }
    }
}

// SharkyClips launcher (1.2.56): what the Start menu / desktop shortcut of the Windows installer runs.
//
//   * Windows-subsystem exe: never a console window.
//   * Starts <app>\python\pythonw.exe <app>\backend\cli.py launch --tray, hidden. The Python side
//     does the rest (splash page, single server per settings folder, tray icon, supervisor).
//   * Single instance: a second double-click while the first one is still starting just asks the
//     running SharkyClips to open its window (cli.py launch reuses the running server).
//   * If Python can't start or ends with an error, an error window shows what happened, with
//     "Copy diagnostic info" (cli.py diag: redacted, no secrets), "Open log folder" and "Try again".
//
// Built by installer/windows/build_installer.py with the csc.exe of the .NET Framework 4.x that is
// part of every Windows 10 / 11 (C# 5: no newer syntax here).

using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;

namespace SharkyClips
{
    internal static class Launcher
    {
        [DllImport("user32.dll")]
        private static extern bool SetProcessDPIAware();

        internal static string AppDir;
        internal static string Home;
        internal static string Lang = "en";

        [STAThread]
        private static int Main(string[] args)
        {
            AppDir = Path.GetDirectoryName(Application.ExecutablePath);
            Home = Environment.GetEnvironmentVariable("SHARKYCLIPS_HOME");
            if (string.IsNullOrEmpty(Home))
                Home = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".sharkyclips");
            Lang = ReadLanguage();
            try { SetProcessDPIAware(); } catch (Exception) { }
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            bool first;
            using (Mutex m = new Mutex(true, "Local\\SharkyClipsLauncher", out first))
            {
                if (!first)
                {
                    // The first launcher is still running (starting, or watching the server): just
                    // ask for the window; cli.py launch opens the running SharkyClips in the browser.
                    int ignored;
                    string ignoredErr;
                    StartPython(new string[] { "launch" }, false, out ignored, out ignoredErr);
                    return 0;
                }
                return RunWatched(args);
            }
        }

        private static int RunWatched(string[] args)
        {
            while (true)
            {
                int code;
                string startError;
                DateTime started = DateTime.Now;
                bool ran = StartPython(new string[] { "launch", "--tray" }, true, out code, out startError);
                Log(string.Format("exit code {0} after {1:0} s{2}", code, (DateTime.Now - started).TotalSeconds,
                                  startError == null ? "" : " (" + startError + ")"));
                if (ran && code == 0)
                    return 0;
                if (UpdateInProgress())
                    return 0; // the installer closed SharkyClips to update it: not an error
                ErrorForm f = new ErrorForm(code, startError);
                Application.Run(f);
                if (!f.TryAgain)
                    return code == 0 ? 1 : code;
            }
        }

        internal static string PythonW { get { return Path.Combine(AppDir, "python", "pythonw.exe"); } }
        internal static string PythonC { get { return Path.Combine(AppDir, "python", "python.exe"); } }
        internal static string Cli { get { return Path.Combine(AppDir, "backend", "cli.py"); } }

        private static bool StartPython(string[] cliArgs, bool wait, out int code, out string error)
        {
            code = -1;
            error = null;
            if (!File.Exists(PythonW) || !File.Exists(Cli))
            {
                error = "missing files: " + (File.Exists(PythonW) ? Cli : PythonW);
                return false;
            }
            ProcessStartInfo psi = new ProcessStartInfo(PythonW, Quote(Cli) + " " + string.Join(" ", cliArgs));
            psi.WorkingDirectory = AppDir;
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            CleanEnvironment(psi);
            try
            {
                using (Process p = Process.Start(psi))
                {
                    Log("started " + string.Join(" ", cliArgs) + " (pid " + p.Id + ")");
                    if (!wait)
                        return true;
                    p.WaitForExit();
                    code = p.ExitCode;
                    return true;
                }
            }
            catch (Exception ex)
            {
                error = ex.GetType().Name + ": " + ex.Message;
                return false;
            }
        }

        internal static void CleanEnvironment(ProcessStartInfo psi)
        {
            // A Python installed on the PC must never leak into the bundled one.
            foreach (string k in new string[] { "PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP", "PYTHONUSERBASE",
                                                "VIRTUAL_ENV", "CONDA_PREFIX" })
                psi.EnvironmentVariables.Remove(k);
            psi.EnvironmentVariables["PYTHONNOUSERSITE"] = "1";
            psi.EnvironmentVariables["PYTHONUTF8"] = "1";
            psi.EnvironmentVariables["SHARKYCLIPS_LAUNCHER"] = Application.ExecutablePath;
        }

        internal static string Quote(string s) { return "\"" + s + "\""; }

        internal static string LogDir { get { return Path.Combine(Home, "logs"); } }

        internal static void Log(string line)
        {
            try
            {
                Directory.CreateDirectory(LogDir);
                string path = Path.Combine(LogDir, "launcher.log");
                FileInfo fi = new FileInfo(path);
                if (fi.Exists && fi.Length > 1000000)
                    File.Delete(path);
                File.AppendAllText(path, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  " + line + Environment.NewLine,
                                   Encoding.UTF8);
            }
            catch (Exception) { }
        }

        private static bool UpdateInProgress()
        {
            // The installer writes this file while it replaces SharkyClips (see SharkyClips.iss).
            string flag = Path.Combine(AppDir, "updating.flag");
            try { return File.Exists(flag) && (DateTime.Now - File.GetLastWriteTime(flag)).TotalMinutes < 30; }
            catch (Exception) { return false; }
        }

        private static string ReadLanguage()
        {
            try
            {
                string cfg = File.ReadAllText(Path.Combine(Home, "config.json"), Encoding.UTF8);
                Match m = Regex.Match(cfg, "\"ui_language\"\\s*:\\s*\"([a-z]{2})");
                if (m.Success)
                    return m.Groups[1].Value;
            }
            catch (Exception) { }
            return Thread.CurrentThread.CurrentUICulture.TwoLetterISOLanguageName == "tr" ? "tr" : "en";
        }

        internal static string T(string en, string tr) { return Lang == "tr" ? tr : en; }

        internal static string LogTail(string file, int lines)
        {
            try
            {
                string path = Path.Combine(LogDir, file);
                if (!File.Exists(path))
                    return "";
                using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                {
                    long start = Math.Max(0, fs.Length - 32 * 1024);
                    fs.Seek(start, SeekOrigin.Begin);
                    using (StreamReader r = new StreamReader(fs, Encoding.UTF8))
                    {
                        string[] all = r.ReadToEnd().Replace("\r", "").Split('\n');
                        int from = Math.Max(0, all.Length - lines);
                        return string.Join(Environment.NewLine, all, from, all.Length - from).Trim();
                    }
                }
            }
            catch (Exception) { return ""; }
        }

        internal static string Anonymize(string text)
        {
            string home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            if (!string.IsNullOrEmpty(home))
                text = text.Replace(home, "~");
            string user = Environment.UserName;
            if (!string.IsNullOrEmpty(user) && user.Length >= 3)
                text = Regex.Replace(text, Regex.Escape(user), "<user>", RegexOptions.IgnoreCase);
            text = Regex.Replace(text, "[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}", "<e-mail>");
            // token-like strings (the Python side's redact.py does the full job when it can run)
            text = Regex.Replace(text, "(ya29\\.|ghp_|github_pat_|GOCSPX-|AIza|EAA|IGQV)[0-9A-Za-z_\\-\\.]{8,}", "[redacted]");
            return text;
        }

        /// The diagnostic text: Python's own report when it can run, else what the launcher knows.
        internal static string Diagnostics(int code, string startError)
        {
            StringBuilder sb = new StringBuilder();
            string pyReport = null;
            if (File.Exists(PythonC) && File.Exists(Cli))
            {
                try
                {
                    ProcessStartInfo psi = new ProcessStartInfo(PythonC, Quote(Cli) + " diag --quick");
                    psi.WorkingDirectory = AppDir;
                    psi.UseShellExecute = false;
                    psi.CreateNoWindow = true;
                    psi.RedirectStandardOutput = true;
                    psi.RedirectStandardError = true;
                    psi.StandardOutputEncoding = Encoding.UTF8;
                    psi.StandardErrorEncoding = Encoding.UTF8;
                    CleanEnvironment(psi);
                    using (Process p = Process.Start(psi))
                    {
                        System.Threading.Tasks.Task<string> err = p.StandardError.ReadToEndAsync();
                        string output = p.StandardOutput.ReadToEnd();
                        if (p.WaitForExit(60000))
                        {
                            pyReport = output.Trim();
                            string e = err.Result.Trim();
                            if (p.ExitCode != 0 && e.Length > 0)
                                pyReport += Environment.NewLine + "diag stderr:" + Environment.NewLine + e;
                        }
                        else
                        {
                            try { p.Kill(); } catch (Exception) { }
                        }
                    }
                }
                catch (Exception ex) { pyReport = "diag failed: " + ex.GetType().Name + ": " + ex.Message; }
            }
            sb.AppendLine("SharkyClips launcher report");
            sb.AppendLine("launcher: " + Application.ProductVersion + "  exit code: " + code +
                          (startError == null ? "" : "  start error: " + startError));
            sb.AppendLine("windows: " + Environment.OSVersion.VersionString + (Environment.Is64BitOperatingSystem ? " 64-bit" : " 32-bit"));
            sb.AppendLine("app folder: " + AppDir);
            if (!string.IsNullOrEmpty(pyReport))
            {
                sb.AppendLine();
                sb.AppendLine(pyReport);
            }
            else
            {
                sb.AppendLine("--- sharkyclips.log ---");
                sb.AppendLine(LogTail("sharkyclips.log", 40));
            }
            sb.AppendLine("--- launcher.log ---");
            sb.AppendLine(LogTail("launcher.log", 10));
            return Anonymize(sb.ToString());
        }
    }

    internal sealed class ErrorForm : Form
    {
        internal bool TryAgain;
        private readonly int code;
        private readonly string startError;

        internal ErrorForm(int code, string startError)
        {
            this.code = code;
            this.startError = startError;
            Text = Launcher.T("SharkyClips couldn't start", "SharkyClips açılamadı");
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch (Exception) { }
            // Sizes are in 96-DPI units; WinForms scales them for the screen (125 %, 150 % ...).
            AutoScaleDimensions = new SizeF(96f, 96f);
            AutoScaleMode = AutoScaleMode.Dpi;
            Font = new Font("Segoe UI", 9.5f);
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(680, 470);
            MinimumSize = new Size(560, 380);
            Padding = new Padding(14);

            Label head = new Label();
            head.Text = Launcher.T("Something went wrong while starting SharkyClips.",
                                   "SharkyClips başlatılırken bir sorun oluştu.");
            head.Font = new Font("Segoe UI Semibold", 12f);
            head.AutoSize = true;
            head.Margin = new Padding(0, 0, 0, 6);

            Label body = new Label();
            body.Text = startError != null && startError.StartsWith("missing files")
                ? Launcher.T("Some SharkyClips files are missing. Download the installer again and run it: your projects and settings are kept.",
                             "Bazı SharkyClips dosyaları eksik. Kurulum dosyasını yeniden indirip çalıştırın: projeleriniz ve ayarlarınız korunur.")
                : Launcher.T("Try again. If it keeps happening, press \"Copy diagnostic info\" and paste it into a bug report on GitHub (it contains no passwords or tokens).",
                             "Tekrar deneyin. Sorun sürerse \"Tanılama bilgisini kopyala\"ya basıp GitHub'da bir hata kaydına yapıştırın (şifre veya anahtar içermez).");
            body.AutoSize = true;
            body.Margin = new Padding(0, 0, 0, 10);

            TextBox log = new TextBox();
            log.Multiline = true;
            log.ReadOnly = true;
            log.ScrollBars = ScrollBars.Both;
            log.WordWrap = false;
            log.Font = new Font("Consolas", 9f);
            log.Dock = DockStyle.Fill;
            log.Margin = new Padding(0, 0, 0, 10);
            string tail = Launcher.LogTail("sharkyclips.log", 30);
            log.Text = Launcher.Anonymize((startError != null ? startError + Environment.NewLine : "") +
                                          (tail.Length > 0 ? tail : Launcher.T("(no log yet)", "(henüz kayıt yok)")) +
                                          Environment.NewLine + "exit code: " + code);
            log.SelectionStart = log.Text.Length;

            FlowLayoutPanel buttons = new FlowLayoutPanel();
            buttons.FlowDirection = FlowDirection.RightToLeft;
            buttons.WrapContents = true;  // narrow window / big text: a second row, never a hidden button
            buttons.AutoSize = true;
            buttons.AutoSizeMode = AutoSizeMode.GrowAndShrink;
            buttons.Dock = DockStyle.Fill;
            buttons.Margin = new Padding(0);

            Button close = MakeButton(Launcher.T("Close", "Kapat"));
            close.Click += delegate { Close(); };
            Button again = MakeButton(Launcher.T("Try again", "Tekrar dene"));
            again.Click += delegate { TryAgain = true; Close(); };
            Button logs = MakeButton(Launcher.T("Open log folder", "Kayıt klasörünü aç"));
            logs.Click += delegate
            {
                try { Directory.CreateDirectory(Launcher.LogDir); Process.Start("explorer.exe", Launcher.Quote(Launcher.LogDir)); }
                catch (Exception) { }
            };
            Button copy = MakeButton(Launcher.T("Copy diagnostic info", "Tanılama bilgisini kopyala"));
            copy.Click += delegate
            {
                Cursor = Cursors.WaitCursor;
                copy.Enabled = false;
                try
                {
                    Clipboard.SetText(Launcher.Diagnostics(this.code, this.startError));
                    copy.Text = Launcher.T("Copied", "Kopyalandı");
                }
                catch (Exception) { copy.Text = Launcher.T("Couldn't copy", "Kopyalanamadı"); }
                finally { Cursor = Cursors.Default; copy.Enabled = true; }
            };
            buttons.Controls.AddRange(new Control[] { close, again, logs, copy });
            AcceptButton = again;
            CancelButton = close;
            TableLayoutPanel table = new TableLayoutPanel();
            table.Dock = DockStyle.Fill;
            table.ColumnCount = 1;
            table.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f));
            table.RowCount = 4;
            table.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            table.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            table.RowStyles.Add(new RowStyle(SizeType.Percent, 100f));
            table.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            table.Controls.Add(head, 0, 0);
            table.Controls.Add(body, 0, 1);
            table.Controls.Add(log, 0, 2);
            table.Controls.Add(buttons, 0, 3);
            Controls.Add(table);
            // labels wrap at the window width (an AutoSize label alone would stay on one line)
            EventHandler wrap = delegate
            {
                int w = Math.Max(100, table.ClientSize.Width - 4);
                head.MaximumSize = new Size(w, 0);
                body.MaximumSize = new Size(w, 0);
            };
            table.Resize += wrap;
            Load += wrap;
        }

        private static Button MakeButton(string text)
        {
            Button b = new Button();
            b.Text = text;
            b.AutoSize = true;
            b.AutoSizeMode = AutoSizeMode.GrowAndShrink;
            b.Padding = new Padding(8, 2, 8, 2);
            b.Margin = new Padding(6, 0, 0, 0);
            return b;
        }
    }
}

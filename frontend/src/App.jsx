import { useState, useEffect } from 'react';
import axios from 'axios';
import { Briefcase, Settings, FileText, Download, Loader2, FileCode } from 'lucide-react';
import FormComponent from './components/Form';
import ReportViewer from './components/ReportViewer';
import ResumeGeneratorForm from './components/ResumeGeneratorForm';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function App() {
  const [activeTab, setActiveTab] = useState('analyzer'); // 'analyzer' or 'generator'
  const [loading, setLoading] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [resumeData, setResumeData] = useState(null);
  const [error, setError] = useState(null);
  const [lmStudioApi, setLmStudioApi] = useState('http://localhost:1234/v1');

  // Load LM Studio API from localStorage on mount
  useEffect(() => {
    const savedApi = localStorage.getItem('lmStudioApi');
    if (savedApi) {
      setLmStudioApi(savedApi);
    }
  }, []);

  const handleLmStudioApiChange = (val) => {
    setLmStudioApi(val);
    localStorage.setItem('lmStudioApi', val);
  };

  const handleAnalyze = async (formData) => {
    setLoading(true);
    setError(null);
    setReportData(null);
    setResumeData(null);
    
    try {
      formData.append('lm_studio_api', lmStudioApi);
      const response = await axios.post('/api/analyze', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setReportData(response.data);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || err.message || 'An error occurred during analysis.');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateResume = async (formData) => {
    setLoading(true);
    setError(null);
    setReportData(null);
    setResumeData(null);
    
    try {
      formData.append('lm_studio_api', lmStudioApi);
      const response = await axios.post('/api/generate_resume', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResumeData(response.data);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || err.message || 'An error occurred during resume generation.');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (filename) => {
    if (!filename) return;
    
    try {
      const response = await axios.get(`/api/download/${filename}`, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
    } catch (err) {
      console.error('Download failed', err);
      alert('Failed to download the file.');
    }
  };

  return (
    <div className="min-h-screen p-4 md:p-8 flex flex-col items-center">
      <header className="relative z-50 w-full max-w-5xl mb-8 flex items-center justify-between glass-card p-6 rounded-xl">
        <div className="flex items-center gap-3">
          <div className="bg-primary/20 p-3 rounded-lg text-primary">
            <Briefcase size={28} />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">Local Job Processor</h1>
            <p className="text-sm text-muted-foreground">AI-powered resume & job matching</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2 relative group">
          <Settings size={20} className="text-muted-foreground cursor-pointer hover:text-white transition-colors" />
          <div className="absolute right-0 top-8 mt-2 w-72 p-4 glass-card rounded-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
            <label className="block text-sm font-medium mb-1">LM Studio API Endpoint</label>
            <input 
              type="text" 
              value={lmStudioApi}
              onChange={(e) => handleLmStudioApiChange(e.target.value)}
              className="w-full p-2 text-sm rounded bg-input border border-border"
              placeholder="http://localhost:1234/v1"
            />
            <p className="text-xs text-muted-foreground mt-2 mb-4">Saved to localStorage automatically.</p>
            <div className="border-t border-border pt-4">
              <label className="block text-sm font-medium mb-1">Database Configuration</label>
              <p className="text-xs text-muted-foreground">
                Please configure your SQL database connection securely using the <code className="bg-muted px-1 py-0.5 rounded text-white">.env</code> file.
              </p>
            </div>
          </div>
        </div>
      </header>

      <main className="w-full max-w-5xl grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div className="lg:col-span-4 flex flex-col gap-6">
          <div className="glass-card p-6 rounded-xl relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-primary to-accent"></div>
            
            <div className="flex border-b border-border/50 mb-6 pb-2 gap-4">
              <button 
                onClick={() => setActiveTab('analyzer')}
                className={`pb-2 text-sm font-semibold transition-colors ${activeTab === 'analyzer' ? 'text-primary border-b-2 border-primary' : 'text-muted-foreground hover:text-white'}`}
              >
                Job Analyzer
              </button>
              <button 
                onClick={() => setActiveTab('generator')}
                className={`pb-2 text-sm font-semibold transition-colors ${activeTab === 'generator' ? 'text-primary border-b-2 border-primary' : 'text-muted-foreground hover:text-white'}`}
              >
                Resume Generator
              </button>
            </div>

            {activeTab === 'analyzer' ? (
              <FormComponent onSubmit={handleAnalyze} isLoading={loading} />
            ) : (
              <ResumeGeneratorForm onSubmit={handleGenerateResume} isLoading={loading} />
            )}
          </div>
        </div>

        <div className="lg:col-span-8 flex flex-col h-full">
          {error && (
            <div className="glass-card border-destructive/50 bg-destructive/10 p-4 rounded-xl mb-6 flex items-start gap-3">
              <div className="text-destructive mt-0.5">⚠️</div>
              <div>
                <h3 className="text-destructive font-semibold">Error</h3>
                <p className="text-sm text-destructive-foreground/90">{error}</p>
              </div>
            </div>
          )}

          {loading ? (
            <div className="glass-card flex-1 min-h-[500px] flex flex-col items-center justify-center rounded-xl">
              <Loader2 className="animate-spin text-primary mb-4" size={48} />
              <h3 className="text-xl font-medium animate-pulse">Processing...</h3>
              <p className="text-muted-foreground mt-2 text-center max-w-sm">
                This might take a few minutes as we query the AI models and process documents.
              </p>
            </div>
          ) : reportData ? (
            <div className="glass-card p-6 md:p-8 rounded-xl flex-1 relative">
              <div className="flex justify-between items-center mb-6 border-b border-border pb-4">
                <h2 className="text-2xl font-bold flex items-center gap-2">
                  <FileText className="text-primary" /> Analysis Report
                </h2>
                {reportData.filename && (
                  <button 
                    onClick={() => handleDownload(reportData.filename)}
                    className="flex items-center gap-2 bg-primary hover:bg-primary/90 text-primary-foreground px-4 py-2 rounded-md font-medium transition-colors shadow-lg shadow-primary/20"
                  >
                    <Download size={18} /> Download .docx
                  </button>
                )}
              </div>
              <ReportViewer data={reportData} />
            </div>
          ) : resumeData ? (
            <div className="glass-card p-6 md:p-8 rounded-xl flex-1 relative overflow-auto">
              <div className="flex justify-between items-center mb-6 border-b border-border pb-4">
                <h2 className="text-2xl font-bold flex items-center gap-2">
                  <FileCode className="text-primary" /> {activeTab === 'generator' ? 'Job & Resume Comparison' : 'Generated Resume'}
                </h2>
                {resumeData.filename && (
                  <button 
                    onClick={() => handleDownload(resumeData.filename)}
                    className="flex items-center gap-2 bg-primary hover:bg-primary/90 text-primary-foreground px-4 py-2 rounded-md font-medium transition-colors shadow-lg shadow-primary/20"
                  >
                    <Download size={18} /> Download .docx
                  </button>
                )}
              </div>
              <div className="prose prose-invert max-w-none text-sm text-gray-200">
                {activeTab === 'generator' && resumeData.comparison ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{resumeData.comparison}</ReactMarkdown>
                ) : (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{resumeData.markdown}</ReactMarkdown>
                )}
              </div>
            </div>
          ) : (
            <div className="glass-card flex-1 min-h-[500px] flex flex-col items-center justify-center rounded-xl text-center p-8 border-dashed border-2 border-border/50 bg-card/20">
              <div className="bg-secondary/30 p-6 rounded-full mb-4">
                <Briefcase size={48} className="text-muted-foreground/50" />
              </div>
              <h3 className="text-xl font-medium text-muted-foreground mb-2">Ready to {activeTab === 'analyzer' ? 'analyze' : 'generate'}</h3>
              <p className="text-sm text-muted-foreground/70 max-w-md">
                Fill out the configuration form on the left and start the process.
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;

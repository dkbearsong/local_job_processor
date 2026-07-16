import { useState } from 'react';
import { FileText, User, Download, Database, FileUp } from 'lucide-react';

const ResumeGeneratorForm = ({ onSubmit, isLoading }) => {
  const [jobSource, setJobSource] = useState('file'); // 'file' or 'sql'
  const [jobId, setJobId] = useState('');
  const [jobDescFile, setJobDescFile] = useState(null);
  const [profileFile, setProfileFile] = useState(null);
  const [folderPath, setFolderPath] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [jobName, setJobName] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    
    const formData = new FormData();
    formData.append('job_source', jobSource);
    if (jobSource === 'file') {
      if (jobDescFile) formData.append('job_desc_file', jobDescFile);
      formData.append('company_name', companyName);
      formData.append('job_name', jobName);
    } else {
      formData.append('job_id', jobId);
    }
    if (profileFile) formData.append('profile_file', profileFile);
    formData.append('folder_path', folderPath);
    
    onSubmit(formData);
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      {/* Job Description Source Selection */}
      <div className="space-y-3">
        <label className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Job Description Source</label>
        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => setJobSource('file')}
            className={`flex flex-col items-center justify-center p-3 rounded-lg border transition-all ${
              jobSource === 'file' 
                ? 'bg-primary/20 border-primary text-primary' 
                : 'bg-card border-border text-muted-foreground hover:bg-muted'
            }`}
          >
            <FileUp size={20} className="mb-1" />
            <span className="text-sm font-medium">Upload File</span>
          </button>
          <button
            type="button"
            onClick={() => setJobSource('sql')}
            className={`flex flex-col items-center justify-center p-3 rounded-lg border transition-all ${
              jobSource === 'sql' 
                ? 'bg-primary/20 border-primary text-primary' 
                : 'bg-card border-border text-muted-foreground hover:bg-muted'
            }`}
          >
            <Database size={20} className="mb-1" />
            <span className="text-sm font-medium">SQL Job ID</span>
          </button>
        </div>
      </div>

      {jobSource === 'file' ? (
        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Job Description File (Required)</label>
            <div className="border-2 border-dashed border-border rounded-lg p-4 flex flex-col items-center justify-center text-center hover:border-primary/50 transition-colors bg-input/50">
              <FileText size={24} className="text-muted-foreground mb-2" />
              <input
                type="file"
                accept=".txt,.pdf,.docx"
                required
                onChange={(e) => setJobDescFile(e.target.files[0])}
                className="text-sm text-muted-foreground file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-primary/20 file:text-primary hover:file:bg-primary/30 w-full"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Company Name (Required)</label>
              <input
                type="text"
                required
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="e.g. Google"
                className="w-full p-2.5 rounded-lg bg-input border border-border focus:ring-2 focus:ring-primary/50 transition-all"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Job Name (Required)</label>
              <input
                type="text"
                required
                value={jobName}
                onChange={(e) => setJobName(e.target.value)}
                placeholder="e.g. Software Engineer"
                className="w-full p-2.5 rounded-lg bg-input border border-border focus:ring-2 focus:ring-primary/50 transition-all"
              />
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <label className="text-sm font-medium">Job ID (Required)</label>
          <input
            type="text"
            required
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
            placeholder="Enter job database ID..."
            className="w-full p-2.5 rounded-lg bg-input border border-border focus:ring-2 focus:ring-primary/50 transition-all"
          />
        </div>
      )}

      <div className="space-y-2">
        <label className="text-sm font-medium">User Profile (Optional)</label>
        <div className="border-2 border-dashed border-border rounded-lg p-4 flex flex-col items-center justify-center text-center hover:border-primary/50 transition-colors bg-input/50">
          <User size={24} className="text-muted-foreground mb-2" />
          <input
            type="file"
            accept=".txt,.pdf,.docx"
            onChange={(e) => setProfileFile(e.target.files[0])}
            className="text-sm text-muted-foreground file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-primary/20 file:text-primary hover:file:bg-primary/30 w-full"
          />
        </div>
        <p className="text-xs text-muted-foreground">If not provided, the default profile from .env will be used.</p>
      </div>

      <div className="space-y-2 pt-2 border-t border-border/50">
        <label className="text-sm font-medium flex items-center gap-1.5">
          <Download size={14} className="text-muted-foreground" /> Output Folder Path (Required)
        </label>
        <input
          type="text"
          required
          value={folderPath}
          onChange={(e) => setFolderPath(e.target.value)}
          placeholder="/path/to/save/directory"
          className="w-full p-2.5 rounded-lg bg-input border border-border focus:ring-2 focus:ring-primary/50 transition-all"
        />
      </div>

      <button
        type="submit"
        disabled={isLoading}
        className="w-full mt-4 bg-primary hover:bg-primary/90 text-white font-medium py-3 rounded-lg transition-all shadow-lg shadow-primary/20 disabled:opacity-50 disabled:cursor-not-allowed flex justify-center items-center gap-2"
      >
        {isLoading ? (
          <>Generating Resume...</>
        ) : (
          <>Generate Resume</>
        )}
      </button>
    </form>
  );
};

export default ResumeGeneratorForm;

import { useState } from 'react';
import { Database, FileSpreadsheet, Search, Building2, Calendar, ListOrdered } from 'lucide-react';

const FormComponent = ({ onSubmit, isLoading }) => {
  const [sourceType, setSourceType] = useState('sql');
  const [searchType, setSearchType] = useState('job');
  const [jobTitle, setJobTitle] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [interval, setInterval] = useState(7);
  const [lim, setLim] = useState(10);
  const [jobLimit, setJobLimit] = useState(3);
  const [csvFile, setCsvFile] = useState(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    
    const formData = new FormData();
    formData.append('search_type', sourceType === 'csv' ? 'csv' : searchType);
    formData.append('job_limit', jobLimit);
    
    if (sourceType === 'csv') {
      if (csvFile) formData.append('csv_file', csvFile);
    } else {
      if (searchType === 'job') formData.append('job_title', jobTitle);
      if (searchType === 'company') formData.append('company_name', companyName);
      formData.append('interval', interval);
      formData.append('lim', lim);
    }
    
    onSubmit(formData);
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      {/* Source Selection */}
      <div className="space-y-3">
        <label className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Data Source</label>
        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => setSourceType('sql')}
            className={`flex flex-col items-center justify-center p-3 rounded-lg border transition-all ${
              sourceType === 'sql' 
                ? 'bg-primary/20 border-primary text-primary' 
                : 'bg-card border-border text-muted-foreground hover:bg-muted'
            }`}
          >
            <Database size={24} className="mb-2" />
            <span className="text-sm font-medium">SQL Database</span>
          </button>
          <button
            type="button"
            onClick={() => setSourceType('csv')}
            className={`flex flex-col items-center justify-center p-3 rounded-lg border transition-all ${
              sourceType === 'csv' 
                ? 'bg-primary/20 border-primary text-primary' 
                : 'bg-card border-border text-muted-foreground hover:bg-muted'
            }`}
          >
            <FileSpreadsheet size={24} className="mb-2" />
            <span className="text-sm font-medium">CSV Upload</span>
          </button>
        </div>
      </div>

      {sourceType === 'sql' ? (
        <>
          {/* Search Type (SQL Only) */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Search By</label>
            <div className="flex bg-input p-1 rounded-lg border border-border">
              <button
                type="button"
                onClick={() => setSearchType('job')}
                className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 text-sm font-medium rounded-md transition-colors ${
                  searchType === 'job' ? 'bg-primary text-white shadow' : 'text-muted-foreground hover:text-white'
                }`}
              >
                <Search size={16} /> Job Title
              </button>
              <button
                type="button"
                onClick={() => setSearchType('company')}
                className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 text-sm font-medium rounded-md transition-colors ${
                  searchType === 'company' ? 'bg-primary text-white shadow' : 'text-muted-foreground hover:text-white'
                }`}
              >
                <Building2 size={16} /> Company
              </button>
            </div>
          </div>

          {/* Search Input */}
          <div className="space-y-2">
            <label className="text-sm font-medium">
              {searchType === 'job' ? 'Job Title' : 'Company Name'}
            </label>
            <input
              type="text"
              required
              value={searchType === 'job' ? jobTitle : companyName}
              onChange={(e) => searchType === 'job' ? setJobTitle(e.target.value) : setCompanyName(e.target.value)}
              placeholder={`Enter ${searchType === 'job' ? 'job title' : 'company name'}...`}
              className="w-full p-2.5 rounded-lg bg-input border border-border focus:ring-2 focus:ring-primary/50 transition-all"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Interval */}
            <div className="space-y-2">
              <label className="text-sm font-medium flex items-center gap-1.5">
                <Calendar size={14} className="text-muted-foreground" /> Days Back
              </label>
              <input
                type="number"
                min="1"
                required
                value={interval}
                onChange={(e) => setInterval(parseInt(e.target.value) || 7)}
                className="w-full p-2.5 rounded-lg bg-input border border-border focus:ring-2 focus:ring-primary/50 transition-all"
              />
            </div>

            {/* Limit SQL Pull */}
            <div className="space-y-2">
              <label className="text-sm font-medium flex items-center gap-1.5">
                <Database size={14} className="text-muted-foreground" /> SQL Limit
              </label>
              <input
                type="number"
                min="1"
                required
                value={lim}
                onChange={(e) => setLim(parseInt(e.target.value) || 10)}
                className="w-full p-2.5 rounded-lg bg-input border border-border focus:ring-2 focus:ring-primary/50 transition-all"
              />
            </div>
          </div>
        </>
      ) : (
        /* CSV Upload Field */
        <div className="space-y-2">
          <label className="text-sm font-medium">Upload CSV File</label>
          <div className="border-2 border-dashed border-border rounded-lg p-6 flex flex-col items-center justify-center text-center hover:border-primary/50 transition-colors bg-input/50">
            <FileSpreadsheet size={32} className="text-muted-foreground mb-3" />
            <input
              type="file"
              accept=".csv"
              required
              onChange={(e) => setCsvFile(e.target.files[0])}
              className="text-sm text-muted-foreground file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-primary/20 file:text-primary hover:file:bg-primary/30 w-full"
            />
          </div>
        </div>
      )}

      {/* Top Jobs Count */}
      <div className="space-y-2 pt-2 border-t border-border/50">
        <label className="text-sm font-medium flex items-center gap-1.5">
          <ListOrdered size={14} className="text-muted-foreground" /> Top Matches to Return
        </label>
        <input
          type="number"
          min="1"
          required
          value={jobLimit}
          onChange={(e) => setJobLimit(parseInt(e.target.value) || 3)}
          className="w-full p-2.5 rounded-lg bg-input border border-border focus:ring-2 focus:ring-primary/50 transition-all"
        />
        <p className="text-xs text-muted-foreground">Number of top matching jobs to analyze against your resume.</p>
      </div>

      <button
        type="submit"
        disabled={isLoading}
        className="w-full mt-4 bg-primary hover:bg-primary/90 text-white font-medium py-3 rounded-lg transition-all shadow-lg shadow-primary/20 disabled:opacity-50 disabled:cursor-not-allowed flex justify-center items-center gap-2"
      >
        {isLoading ? (
          <>Processing Data...</>
        ) : (
          <>Run Analysis</>
        )}
      </button>
    </form>
  );
};

export default FormComponent;

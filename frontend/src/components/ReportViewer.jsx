import ReactMarkdown from 'react-markdown';
import { Target, Lightbulb, UserCheck, Edit3 } from 'lucide-react';

const ReportViewer = ({ data }) => {
  if (!data) return null;

  const { job_title, company_name, common_skills, projects, matches, adjustments } = data;

  return (
    <div className="space-y-8 overflow-y-auto pr-2 custom-scrollbar" style={{ maxHeight: 'calc(100vh - 250px)' }}>
      
      {/* Header Info */}
      {(job_title || company_name) && (
        <div className="flex flex-wrap gap-4 mb-6">
          {job_title && (
            <div className="bg-primary/10 border border-primary/20 text-primary px-4 py-2 rounded-lg inline-block">
              <span className="text-xs uppercase tracking-wider font-semibold opacity-80 block mb-0.5">Target Job</span>
              <span className="font-medium text-lg">{job_title}</span>
            </div>
          )}
          {company_name && (
            <div className="bg-accent/10 border border-accent/20 text-accent px-4 py-2 rounded-lg inline-block">
              <span className="text-xs uppercase tracking-wider font-semibold opacity-80 block mb-0.5">Target Company</span>
              <span className="font-medium text-lg">{company_name}</span>
            </div>
          )}
        </div>
      )}

      {/* Top Matches Section */}
      {matches && matches.length > 0 && (
        <section className="space-y-4">
          <h3 className="text-xl font-semibold flex items-center gap-2 border-b border-border/50 pb-2">
            <UserCheck className="text-primary" size={20} /> Personalized Career Matches
          </h3>
          <div className="grid gap-4">
            {matches.map((match, idx) => (
              <div key={idx} className="bg-card border border-border p-5 rounded-lg hover:border-primary/50 transition-colors">
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h4 className="text-lg font-medium text-white">{match.job_name}</h4>
                    <p className="text-muted-foreground">{match.company_name} <span className="opacity-50 mx-1">•</span> ID: {match.job_id}</p>
                  </div>
                  <div className={`px-3 py-1 rounded-full text-sm font-bold flex items-center gap-1 ${
                    match.match_score >= 80 ? 'bg-green-500/20 text-green-400' : 
                    match.match_score >= 50 ? 'bg-yellow-500/20 text-yellow-400' : 
                    'bg-destructive/20 text-destructive'
                  }`}>
                    {match.match_score}% Match
                  </div>
                </div>
                
                <p className="text-sm text-foreground/90 mt-3">{match.reasoning}</p>
                
                <div className="grid grid-cols-2 gap-4 mt-4">
                  {match.matching_skills?.length > 0 && (
                    <div className="bg-green-500/5 rounded border border-green-500/10 p-3">
                      <span className="text-xs text-green-400 font-semibold uppercase mb-2 block">Matching Skills</span>
                      <div className="flex flex-wrap gap-1.5">
                        {match.matching_skills.map((skill, sIdx) => (
                          <span key={sIdx} className="text-xs bg-green-500/20 text-green-300 px-2 py-0.5 rounded">{skill}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {match.missing_skills?.length > 0 && (
                    <div className="bg-destructive/5 rounded border border-destructive/10 p-3">
                      <span className="text-xs text-destructive font-semibold uppercase mb-2 block">Missing Skills</span>
                      <div className="flex flex-wrap gap-1.5">
                        {match.missing_skills.map((skill, sIdx) => (
                          <span key={sIdx} className="text-xs bg-destructive/20 text-destructive px-2 py-0.5 rounded">{skill}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Resume Adjustments Section */}
      {adjustments && (
        <section className="space-y-4">
          <h3 className="text-xl font-semibold flex items-center gap-2 border-b border-border/50 pb-2">
            <Edit3 className="text-accent" size={20} /> Resume Adjustments
          </h3>
          <div className="prose prose-invert max-w-none bg-card/50 p-5 rounded-lg border border-border/50 prose-a:text-primary">
            <ReactMarkdown>{adjustments}</ReactMarkdown>
          </div>
        </section>
      )}

      {/* Skills & Responsibilities Section */}
      {common_skills && (
        <section className="space-y-4">
          <h3 className="text-xl font-semibold flex items-center gap-2 border-b border-border/50 pb-2">
            <Target className="text-primary" size={20} /> Skills & Requirements
          </h3>
          <div className="prose prose-invert max-w-none bg-card/50 p-5 rounded-lg border border-border/50 prose-a:text-primary">
            <ReactMarkdown>{common_skills}</ReactMarkdown>
          </div>
        </section>
      )}

      {/* Suggested Projects Section */}
      {projects && (
        <section className="space-y-4">
          <h3 className="text-xl font-semibold flex items-center gap-2 border-b border-border/50 pb-2">
            <Lightbulb className="text-yellow-400" size={20} /> Suggested Projects
          </h3>
          <div className="prose prose-invert max-w-none bg-card/50 p-5 rounded-lg border border-border/50 prose-a:text-primary">
            <ReactMarkdown>{projects}</ReactMarkdown>
          </div>
        </section>
      )}

    </div>
  );
};

export default ReportViewer;

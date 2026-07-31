import React, { useState, useEffect } from 'react';
import { 
  Key, 
  Plus, 
  Trash2, 
  Copy, 
  Check, 
  AlertCircle
} from 'lucide-react';
import { toast } from 'sonner';
import { API_BASE_URL } from '@/config';

export default function ApiKeys() {
  const [apiKeys, setApiKeys] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [newKeyName, setNewKeyName] = useState('');
  const [copied, setCopied] = useState(null);
  const [newlyCreatedKey, setNewlyCreatedKey] = useState(null);
  const [isCreating, setIsCreating] = useState(false);

  const fetchKeys = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/keys`, { credentials: 'include' });
      if (res.ok) {
        setApiKeys(await res.json());
      }
    } catch (e) {
      toast.error('Failed to load API keys');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchKeys();
  }, []);

  const handleCreate = async () => {
    if (!newKeyName.trim() || isCreating) return;
    setIsCreating(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ name: newKeyName.trim() })
      });
      if (res.ok) {
        const data = await res.json();
        setNewlyCreatedKey(data.raw_key);
        setNewKeyName('');
        fetchKeys();
        toast.success('API Key created successfully');
      } else {
        toast.error('Failed to create API key');
      }
    } catch (e) {
      toast.error('Failed to create API key');
    } finally {
      setIsCreating(false);
    }
  };

  const handleRevoke = async (id) => {
    if (!window.confirm('Are you sure you want to revoke this API key? This action cannot be undone.')) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/keys/${id}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      if (res.ok) {
        fetchKeys();
        toast.success('API Key revoked');
      } else {
        toast.error('Failed to revoke API key');
      }
    } catch (e) {
      toast.error('Failed to revoke API key');
    }
  };

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          <Key className="h-6 w-6 text-indigo-400" />
          API Keys
        </h1>
        <p className="text-gray-400 mt-2">
          Manage API keys for programmatic access to your Orkestra agents.
        </p>
      </div>

      {newlyCreatedKey && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4 flex flex-col gap-3">
          <div className="flex items-center gap-2 text-green-400 font-medium">
            <AlertCircle className="h-5 w-5" />
            Please copy your API key now
          </div>
          <p className="text-sm text-green-200/70">
            For security reasons, this is the only time it will be shown. If you lose it, you'll need to generate a new one.
          </p>
          <div className="flex items-center gap-2 bg-black/50 p-3 rounded border border-green-500/20">
            <code className="text-green-300 flex-1 font-mono">{newlyCreatedKey}</code>
            <button 
              onClick={() => copyToClipboard(newlyCreatedKey, 'new')}
              className="text-gray-400 hover:text-white transition-colors"
            >
              {copied === 'new' ? <Check className="h-4 w-4 text-green-400" /> : <Copy className="h-4 w-4" />}
            </button>
          </div>
          <button 
            onClick={() => setNewlyCreatedKey(null)}
            className="text-sm text-green-400 hover:text-green-300 self-start mt-1 font-medium"
          >
            I have saved it securely
          </button>
        </div>
      )}

      <div className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-5">
        <h2 className="text-lg font-medium text-white mb-4">Create New API Key</h2>
        <div className="flex gap-3">
          <input
            type="text"
            value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
            placeholder="e.g. My Production App"
            className="flex-1 bg-gray-900/50 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            onKeyDown={(e) => e.key === 'Enter' && newKeyName.trim() && handleCreate()}
          />
          <button
            onClick={handleCreate}
            disabled={!newKeyName.trim() || isCreating}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Plus className="h-4 w-4" />
            Create Key
          </button>
        </div>
      </div>

      <div className="bg-gray-800/50 border border-gray-700/50 rounded-lg overflow-hidden">
        <table className="w-full text-left">
          <thead className="bg-gray-900/50 text-gray-400 text-sm">
            <tr>
              <th className="px-6 py-4 font-medium">Name</th>
              <th className="px-6 py-4 font-medium">Key Prefix</th>
              <th className="px-6 py-4 font-medium">Created</th>
              <th className="px-6 py-4 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700/50">
            {isLoading ? (
              <tr>
                <td colSpan="4" className="px-6 py-8 text-center text-gray-500">Loading...</td>
              </tr>
            ) : apiKeys.length === 0 ? (
              <tr>
                <td colSpan="4" className="px-6 py-8 text-center text-gray-500">No API keys generated yet.</td>
              </tr>
            ) : (
              apiKeys.map((key) => (
                <tr key={key.id} className={`group ${!key.is_active ? 'opacity-50' : ''}`}>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-white">{key.name}</span>
                      {!key.is_active && (
                        <span className="px-2 py-0.5 rounded text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20">
                          Revoked
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-gray-300 font-mono text-sm">
                    {key.prefix}••••••••••••••••
                  </td>
                  <td className="px-6 py-4 text-gray-400 text-sm">
                    {new Date(key.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 text-right">
                    {key.is_active && (
                      <button
                        onClick={() => handleRevoke(key.id)}
                        className="text-gray-500 hover:text-red-400 transition-colors p-2 rounded-lg hover:bg-red-500/10"
                        title="Revoke Key"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

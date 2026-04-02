import { useState } from 'react';
import { Upload, FileText, Image } from 'lucide-react';

function App() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDownload = async (endpoint: string, modelType: string) => {
    if (!selectedFile) return;

    setIsProcessing(true);
    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await fetch(`https://sritharoonhf-boozo.hf.space/${endpoint}`, {
  method: 'POST',
  body: formData,
  mode: "cors",
});

      if (!response.ok) {
        const error = await response.json();
        alert(`Error: ${error.error}`);
        return;
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Extracted_Data_${modelType}.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      alert(`Error: ${error instanceof Error ? error.message : 'Failed to process file'}`);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
      <div className="flex">
        <aside className="w-64 min-h-screen bg-gradient-to-b from-blue-400 to-purple-400 p-6 shadow-xl">
          <div className="flex items-center space-x-3 mb-8">
            <div className="w-10 h-10 bg-white rounded-full flex items-center justify-center">
              <FileText className="w-6 h-6 text-blue-600" />
            </div>
            <h1 className="text-white font-bold text-xl">Data Extractor</h1>
          </div>

          <nav className="space-y-2">
            <div className="bg-white bg-opacity-20 text-white px-4 py-3 rounded-lg font-medium">
              Home
            </div>
            <div className="text-white text-opacity-80 px-4 py-3 rounded-lg hover:bg-white hover:bg-opacity-10 transition cursor-pointer">
              History
            </div>
            <div className="text-white text-opacity-80 px-4 py-3 rounded-lg hover:bg-white hover:bg-opacity-10 transition cursor-pointer">
              Settings
            </div>
          </nav>
        </aside>

        <main className="flex-1 p-12">
          <div className="max-w-4xl mx-auto">
            <div className="mb-8">
              <h2 className="text-4xl font-bold text-gray-800 mb-2">Upload Your Document</h2>
              <p className="text-gray-600">Upload your payroll document and extract data using AI models</p>
            </div>

            <div className="bg-white rounded-2xl shadow-xl p-8 mb-6">
              <div
                className={`border-2 border-dashed rounded-xl p-12 text-center transition-all ${
                  isDragging
                    ? 'border-blue-500 bg-blue-50'
                    : selectedFile
                    ? 'border-green-400 bg-green-50'
                    : 'border-gray-300 hover:border-blue-400'
                }`}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
              >
                <div className="flex flex-col items-center justify-center space-y-4">
                  <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center">
                    <Upload className="w-10 h-10 text-white" />
                  </div>

                  {selectedFile ? (
                    <div className="text-center">
                      <p className="text-lg font-semibold text-gray-800 mb-1">File Selected</p>
                      <p className="text-sm text-gray-600">{selectedFile.name}</p>
                      <p className="text-xs text-gray-500 mt-1">
                        {(selectedFile.size / 1024).toFixed(2)} KB
                      </p>
                    </div>
                  ) : (
                    <div className="text-center">
                      <p className="text-lg font-semibold text-gray-800 mb-1">
                        Select Document to Upload
                      </p>
                      <p className="text-sm text-gray-600">
                        Supported Format: PDF (10mb max)
                      </p>
                    </div>
                  )}

                  <label className="cursor-pointer">
                    <span className="inline-block bg-gradient-to-r from-blue-600 to-purple-600 text-white px-8 py-3 rounded-full font-medium hover:shadow-lg transform hover:scale-105 transition-all">
                      {selectedFile ? 'Change File' : 'Select File'}
                    </span>
                    <input
                      type="file"
                      className="hidden"
                      accept=".pdf,image/*"
                      onChange={handleFileChange}
                    />
                  </label>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-2xl shadow-xl p-8">
              <h3 className="text-xl font-bold text-gray-800 mb-4">Choose Processing Method</h3>
              <p className="text-gray-600 mb-6">Select which AI model to use for data extraction</p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <button
                  onClick={() => handleDownload('download_with_image_model', 'Gemini')}
                  disabled={!selectedFile || isProcessing}
                  className={`p-6 rounded-xl border-2 text-left transition-all ${
                    selectedFile && !isProcessing
                      ? 'border-blue-500 bg-blue-50 hover:shadow-lg hover:scale-105 cursor-pointer'
                      : 'border-gray-200 bg-gray-50 opacity-50 cursor-not-allowed'
                  }`}
                >
                  <div className="flex items-start space-x-4">
                    <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg flex items-center justify-center flex-shrink-0">
                      <Image className="w-6 h-6 text-white" />
                    </div>
                    <div className="flex-1">
                      <h4 className="font-bold text-gray-800 mb-1">Image Model</h4>
                      <p className="text-sm text-gray-600">
                        Uses Gemini 1.5 Flash for visual document processing
                      </p>
                    </div>
                  </div>
                </button>

                <button
                  onClick={() => handleDownload('download_with_text_model', 'Groq')}
                  disabled={!selectedFile || isProcessing}
                  className={`p-6 rounded-xl border-2 text-left transition-all ${
                    selectedFile && !isProcessing
                      ? 'border-purple-500 bg-purple-50 hover:shadow-lg hover:scale-105 cursor-pointer'
                      : 'border-gray-200 bg-gray-50 opacity-50 cursor-not-allowed'
                  }`}
                >
                  <div className="flex items-start space-x-4">
                    <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg flex items-center justify-center flex-shrink-0">
                      <FileText className="w-6 h-6 text-white" />
                    </div>
                    <div className="flex-1">
                      <h4 className="font-bold text-gray-800 mb-1">Text Model</h4>
                      <p className="text-sm text-gray-600">
                        Uses Groq Llama3 for text-based document processing
                      </p>
                    </div>
                  </div>
                </button>
              </div>

              {isProcessing && (
                <div className="mt-6 text-center">
                  <div className="inline-flex items-center space-x-3 bg-blue-50 px-6 py-3 rounded-full">
                    <div className="w-5 h-5 border-3 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                    <span className="text-blue-700 font-medium">Processing your document...</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;

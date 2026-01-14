'use client';

import { useState } from 'react';
import { Play, Image, Sparkles, Zap, CheckCircle2, AlertCircle, Info } from 'lucide-react';

export default function AvatarGuidePage() {
    const [activeTab, setActiveTab] = useState<'overview' | 'howto' | 'tips'>('overview');

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
            <div className="max-w-6xl mx-auto px-6 py-12">
                {/* Header */}
                <div className="text-center mb-12">
                    <div className="inline-flex items-center gap-2 px-4 py-2 bg-purple-100 dark:bg-purple-900/30 rounded-full mb-4">
                        <Sparkles className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                        <span className="text-sm font-medium text-purple-700 dark:text-purple-300">
                            Powered by SadTalker AI
                        </span>
                    </div>

                    <h1 className="text-5xl font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent mb-4">
                        Talking Avatars
                    </h1>
                    <p className="text-xl text-slate-600 dark:text-slate-300 max-w-2xl mx-auto">
                        Transform any photo into a lifelike talking avatar with realistic facial expressions,
                        natural head movements, and emotion-aware animations.
                    </p>
                </div>

                {/* Tabs */}
                <div className="flex gap-2 mb-8 border-b border-slate-200 dark:border-slate-700">
                    {[
                        { id: 'overview', label: 'Overview' },
                        { id: 'howto', label: 'How to Create' },
                        { id: 'tips', label: 'Best Practices' },
                    ].map((tab) => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id as any)}
                            className={`px-6 py-3 font-medium transition-colors ${activeTab === tab.id
                                    ? 'text-purple-600 dark:text-purple-400 border-b-2 border-purple-600'
                                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                                }`}
                        >
                            {tab.label}
                        </button>
                    ))}
                </div>

                {/* Content */}
                <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-8">
                    {activeTab === 'overview' && <OverviewTab />}
                    {activeTab === 'howto' && <HowToTab />}
                    {activeTab === 'tips' && <TipsTab />}
                </div>
            </div>
        </div>
    );
}

function OverviewTab() {
    return (
        <div className="space-y-8">
            <section>
                <h2 className="text-3xl font-bold mb-4">What are Talking Avatars?</h2>
                <p className="text-lg text-slate-600 dark:text-slate-300 mb-6">
                    Talking avatars bring static images to life by synchronizing mouth movements with audio,
                    adding natural facial expressions, and generating realistic head movements—all powered by
                    advanced AI.
                </p>

                {/* Feature Comparison */}
                <div className="grid md:grid-cols-2 gap-6 mt-8">
                    <FeatureCard
                        title="Basic Mode (Wav2Lip)"
                        icon={<Zap className="w-6 h-6" />}
                        features={[
                            'Precise lip synchronization',
                            'Fast generation (< 1 min)',
                            'Lower resource usage',
                            'Good for quick previews'
                        ]}
                        color="blue"
                    />
                    <FeatureCard
                        title="Enhanced Mode (SadTalker)"
                        icon={<Sparkles className="w-6 h-6" />}
                        features={[
                            'Emotion-aware facial expressions',
                            'Natural head movements',
                            'Contextual micro-expressions',
                            'Premium quality output'
                        ]}
                        color="purple"
                        recommended
                    />
                </div>
            </section>

            <section className="pt-8 border-t border-slate-200 dark:border-slate-700">
                <h2 className="text-2xl font-bold mb-4">Key Features</h2>
                <div className="grid md:grid-cols-3 gap-4">
                    <InfoCard
                        icon={<Image className="w-5 h-5" />}
                        title="Any Photo Works"
                        description="Upload selfies, professional headshots, or even historical photos"
                    />
                    <InfoCard
                        icon={<Sparkles className="w-5 h-5" />}
                        title="Auto Emotion Detection"
                        description="AI analyzes your script to apply appropriate facial expressions"
                    />
                    <InfoCard
                        icon={<Play className="w-5 h-5" />}
                        title="Realistic Movement"
                        description="Natural head tilts, nods, and micro-movements make avatars lifelike"
                    />
                </div>
            </section>
        </div>
    );
}

function HowToTab() {
    const steps = [
        {
            number: 1,
            title: 'Upload Your Photo',
            description: 'Choose a clear, front-facing photo with good lighting. The AI works best with high-resolution images where the face is clearly visible.',
            tips: [
                'Minimum resolution: 512x512px',
                'Face should occupy 40-60% of the image',
                'Avoid sunglasses, masks, or heavy shadows',
                'Neutral expression recommended for source image'
            ]
        },
        {
            number: 2,
            title: 'Write Your Script',
            description: 'Create the text your avatar will speak. The AI will automatically detect emotions and apply appropriate expressions.',
            tips: [
                'Use natural, conversational language',
                'Add emotion hints: "I\'m so excited!" triggers happy expressions',
                'Keep sentences clear and well-paced',
                'Preview with a short script first'
            ]
        },
        {
            number: 3,
            title: 'Configure Settings',
            description: 'Choose between Basic (fast) or Enhanced (high quality) mode. Adjust expression and movement intensity to your preference.',
            tips: [
                'Start with default settings (1.0x)',
                'Increase expression scale for more dramatic emotions',
                'Reduce head pose scale for formal/professional videos',
                'Use Basic mode for quick previews'
            ]
        },
        {
            number: 4,
            title: 'Generate & Download',
            description: 'Click generate and wait for your avatar video. Enhanced mode takes longer but produces significantly better results.',
            tips: [
                'Basic mode: ~1 minute for 1 minute of video',
                'Enhanced mode: ~2-3 minutes for 1 minute of video',
                'Videos are saved in your library',
                'Download in multiple resolutions'
            ]
        }
    ];

    return (
        <div className="space-y-8">
            <h2 className="text-3xl font-bold mb-6">Step-by-Step Guide</h2>
            {steps.map((step) => (
                <StepCard key={step.number} {...step} />
            ))}
        </div>
    );
}

function TipsTab() {
    return (
        <div className="space-y-8">
            <section>
                <h2 className="text-3xl font-bold mb-6">Best Practices</h2>

                <div className="space-y-6">
                    <TipSection
                        title="Photo Selection"
                        icon={<CheckCircle2 className="w-5 h-5 text-green-500" />}
                        tips={[
                            'Use high-quality, well-lit photos (natural light is best)',
                            'Ensure the face is centered and clearly visible',
                            'Avoid extreme angles or side profiles',
                            'Professional headshots work exceptionally well',
                            'Remove backgrounds for cleaner results (optional)'
                        ]}
                    />

                    <TipSection
                        title="Script Writing"
                        icon={<CheckCircle2 className="w-5 h-5 text-green-500" />}
                        tips={[
                            'Write in a natural, conversational tone',
                            'Use punctuation to control pacing (commas = pauses)',
                            'Include emotion keywords: "excited", "concerned", "happy"',
                            'Keep sentences concise for better lip-sync',
                            'Test with a short preview before full generation'
                        ]}
                    />

                    <TipSection
                        title="Quality Optimization"
                        icon={<CheckCircle2 className="w-5 h-5 text-green-500" />}
                        tips={[
                            'Use Enhanced mode (SadTalker) for final videos',
                            'Start with Basic mode for quick iterations',
                            'Higher resolution = better quality but slower generation',
                            'Expression scale 1.0-1.5x works for most use cases',
                            'Head pose scale 0.8-1.2x for natural movement'
                        ]}
                    />

                    <TipSection
                        title="Common Pitfalls to Avoid"
                        icon={<AlertCircle className="w-5 h-5 text-amber-500" />}
                        tips={[
                            'Don\'t use blurry or low-resolution photos',
                            'Avoid photos with multiple faces (use cropped version)',
                            'Don\'t write overly long scripts (break into segments)',
                            'Avoid extreme lighting conditions in source photos',
                            'Don\'t set expression/pose scales too high (looks unnatural)'
                        ]}
                    />
                </div>
            </section>

            <section className="pt-8 border-t border-slate-200 dark:border-slate-700">
                <h2 className="text-2xl font-bold mb-4">Pro Tips</h2>
                <div className="bg-gradient-to-r from-purple-50 to-pink-50 dark:from-purple-900/20 dark:to-pink-900/20 rounded-xl p-6">
                    <div className="flex items-start gap-3">
                        <Info className="w-5 h-5 text-purple-600 dark:text-purple-400 mt-0.5 flex-shrink-0" />
                        <div className="space-y-2 text-sm text-slate-700 dark:text-slate-300">
                            <p><strong>Emotion Mixing:</strong> The AI can blend emotions. Try "I'm cautiously optimistic" for nuanced expressions.</p>
                            <p><strong>Batch Processing:</strong> Create multiple avatars with different emotions from the same photo.</p>
                            <p><strong>Voice Cloning:</strong> Combine with our TTS voice cloning for personalized avatars.</p>
                            <p><strong>A/B Testing:</strong> Generate both Basic and Enhanced versions to compare quality vs speed.</p>
                        </div>
                    </div>
                </div>
            </section>
        </div>
    );
}

// Helper Components
function FeatureCard({ title, icon, features, color, recommended }: any) {
    const colorClasses = {
        blue: 'from-blue-500 to-cyan-500',
        purple: 'from-purple-500 to-pink-500'
    };

    return (
        <div className={`relative rounded-xl border-2 ${recommended ? 'border-purple-500 dark:border-purple-400' : 'border-slate-200 dark:border-slate-700'} p-6 hover:shadow-lg transition-shadow`}>
            {recommended && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-gradient-to-r from-purple-500 to-pink-500 text-white text-xs font-bold rounded-full">
                    RECOMMENDED
                </div>
            )}
            <div className={`inline-flex p-3 rounded-lg bg-gradient-to-r ${colorClasses[color]} text-white mb-4`}>
                {icon}
            </div>
            <h3 className="text-xl font-bold mb-3">{title}</h3>
            <ul className="space-y-2">
                {features.map((feature: string, i: number) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
                        <CheckCircle2 className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
                        <span>{feature}</span>
                    </li>
                ))}
            </ul>
        </div>
    );
}

function InfoCard({ icon, title, description }: any) {
    return (
        <div className="p-4 rounded-lg bg-slate-50 dark:bg-slate-700/50">
            <div className="flex items-center gap-2 mb-2 text-purple-600 dark:text-purple-400">
                {icon}
                <h3 className="font-semibold">{title}</h3>
            </div>
            <p className="text-sm text-slate-600 dark:text-slate-300">{description}</p>
        </div>
    );
}

function StepCard({ number, title, description, tips }: any) {
    return (
        <div className="flex gap-6">
            <div className="flex-shrink-0 w-12 h-12 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 flex items-center justify-center text-white font-bold text-xl">
                {number}
            </div>
            <div className="flex-1">
                <h3 className="text-xl font-bold mb-2">{title}</h3>
                <p className="text-slate-600 dark:text-slate-300 mb-4">{description}</p>
                <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-4">
                    <p className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">Tips:</p>
                    <ul className="space-y-1">
                        {tips.map((tip: string, i: number) => (
                            <li key={i} className="text-sm text-slate-600 dark:text-slate-400 flex items-start gap-2">
                                <span className="text-purple-500">•</span>
                                <span>{tip}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            </div>
        </div>
    );
}

function TipSection({ title, icon, tips }: any) {
    return (
        <div>
            <div className="flex items-center gap-2 mb-3">
                {icon}
                <h3 className="text-lg font-bold">{title}</h3>
            </div>
            <ul className="space-y-2 ml-7">
                {tips.map((tip: string, i: number) => (
                    <li key={i} className="text-slate-600 dark:text-slate-300 flex items-start gap-2">
                        <span className="text-purple-500 mt-1">•</span>
                        <span>{tip}</span>
                    </li>
                ))}
            </ul>
        </div>
    );
}

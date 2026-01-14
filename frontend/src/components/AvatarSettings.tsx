import React from 'react';
import { Label } from '@/components/ui/label';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
// import { Switch } from '@/components/ui/switch';
import { Card, CardContent } from '@/components/ui/card';
import { Info, Sparkles, Smile, Frame, Maximize2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface AvatarSettingsProps {
    emotion: string;
    setEmotion: (value: string) => void;
    expressionScale: number;
    setExpressionScale: (value: number) => void;
    useEnhancer: boolean;
    setUseEnhancer: (value: boolean) => void;
    preprocess: string;
    setPreprocess: (value: string) => void;
    disabled?: boolean;
}

export function AvatarSettings({
    emotion,
    setEmotion,
    expressionScale,
    setExpressionScale,
    useEnhancer,
    setUseEnhancer,
    preprocess,
    setPreprocess,
    disabled
}: AvatarSettingsProps) {
    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-neura-500" />
                    Advanced Avatar Model
                </h3>
                <span className="text-xs bg-neura-500/10 text-neura-500 px-2 py-1 rounded-full">
                    SadTalker + GFPGAN
                </span>
            </div>

            <div className="grid gap-6">
                {/* Emotion */}
                <div className="space-y-3">
                    <Label className="flex items-center gap-2">
                        <Smile className="w-4 h-4" />
                        Emotion
                    </Label>
                    <Select
                        value={emotion}
                        onValueChange={setEmotion}
                        disabled={disabled}
                    >
                        <SelectTrigger>
                            <SelectValue placeholder="Select emotion" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="neutral">Neutral (Default)</SelectItem>
                            <SelectItem value="happy">Happy</SelectItem>
                            <SelectItem value="sad">Sad</SelectItem>
                            <SelectItem value="angry">Angry</SelectItem>
                            <SelectItem value="surprised">Surprised</SelectItem>
                        </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                        Sets the emotional tone of the avatar's speech.
                    </p>
                </div>

                {/* Expression Scale (Teeth Visibility) */}
                <div className="space-y-4">
                    <div className="flex justify-between items-center">
                        <Label className="flex items-center gap-2">
                            Expression Intensity
                        </Label>
                        <span className="text-xs font-mono bg-muted px-2 py-1 rounded">
                            {expressionScale.toFixed(1)}
                        </span>
                    </div>
                    <Slider
                        value={[expressionScale]}
                        min={0.5}
                        max={2.0}
                        step={0.1}
                        onValueChange={(vals) => setExpressionScale(vals[0])}
                        disabled={disabled}
                    />
                    <p className="text-xs text-muted-foreground flex items-start gap-2">
                        <Info className="w-4 h-4 flex-shrink-0" />
                        Higher values (1.3+) increase mouth opening and visible teeth. Using 1.3 is recommended for "Wavespeed" style.
                    </p>
                </div>

                {/* Framing / Preprocess */}
                <div className="space-y-3">
                    <Label className="flex items-center gap-2">
                        <Frame className="w-4 h-4" />
                        Framing & Resolution
                    </Label>
                    <div className="grid grid-cols-2 gap-4">
                        <Card
                            className={`cursor-pointer transition border-2 ${preprocess === 'full' ? 'border-primary bg-primary/5' : 'border-transparent hover:border-primary/50'}`}
                            onClick={() => !disabled && setPreprocess('full')}
                        >
                            <CardContent className="p-4 flex flex-col items-center justify-center gap-2 text-center">
                                <Maximize2 className="w-6 h-6" />
                                <span className="font-medium text-sm">Full Frame</span>
                                <span className="text-xs text-muted-foreground">Preserves original 1080p background</span>
                            </CardContent>
                        </Card>
                        <Card
                            className={`cursor-pointer transition border-2 ${preprocess === 'crop' ? 'border-primary bg-primary/5' : 'border-transparent hover:border-primary/50'}`}
                            onClick={() => !disabled && setPreprocess('crop')}
                        >
                            <CardContent className="p-4 flex flex-col items-center justify-center gap-2 text-center">
                                <Frame className="w-6 h-6" />
                                <span className="font-medium text-sm">Face Crop</span>
                                <span className="text-xs text-muted-foreground">Square video, focus on face only</span>
                            </CardContent>
                        </Card>
                    </div>
                </div>

                {/* Enhancer Toggle */}
                <div className="flex items-center justify-between p-4 border rounded-lg bg-card">
                    <div className="space-y-0.5">
                        <Label className="flex items-center gap-2">
                            <Sparkles className="w-4 h-4 text-amber-500" />
                            Face Enhancer (GFPGAN)
                        </Label>
                        <p className="text-xs text-muted-foreground">
                            Upscales and restores face details. Highly recommended.
                        </p>
                    </div>
                    <Button
                        variant={useEnhancer ? "default" : "outline"}
                        onClick={() => !disabled && setUseEnhancer(!useEnhancer)}
                        className="w-20"
                    >
                        {useEnhancer ? "ON" : "OFF"}
                    </Button>
                </div>
            </div>
        </div>
    );
}
